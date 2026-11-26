"""Booking rules shared by the agent's tools and the booking API.

Square stays the source of truth: availability is always read live, and a slot is
re-checked right before booking.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Literal

from agent_service.square.backend import BookingBackend
from agent_service.square.models import Booking, Customer, Service, Slot
from agent_service.square.times import day_range

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class BookingError(Exception):
    """A problem the client can fix (not a Square or server failure)."""

    def __init__(self, code: Literal["slot_taken", "name_required", "bad_time"], message: str):
        super().__init__(message)
        self.code = code


def open_slots(
    backend: BookingBackend, service: Service, first: date, last: date, now: Clock = utc_now
) -> list[Slot]:
    """Open slots from the start of `first` to the end of `last` (local days), never in the past."""
    tz = backend.tz
    start = max(day_range(first, tz)[0], now().astimezone(tz))
    end = day_range(last, tz)[1]
    if end <= start:
        return []
    return backend.find_availability(service, start, end)


def parse_local_time(value: str, backend: BookingBackend) -> datetime:
    """Parse YYYY-MM-DDTHH:MM as shop-local time (an explicit offset is respected)."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise BookingError("bad_time", "Times must look like 2026-11-28T11:30.") from error
    return parsed.astimezone(backend.tz) if parsed.tzinfo else parsed.replace(tzinfo=backend.tz)


def book(
    backend: BookingBackend,
    service: Service,
    start: datetime,
    phone: str,
    first_name: str | None = None,
    last_name: str | None = None,
    note: str | None = None,
    now: Clock = utc_now,
) -> tuple[Booking, Customer]:
    """Re-check the slot, find or create the client, then book.

    Raises BookingError for problems the client can fix, SquareError for Square failures
    and ValueError for an invalid phone number.
    """
    day = start.astimezone(backend.tz).date()
    slot = next(
        (s for s in open_slots(backend, service, day, day, now) if s.start_at == start), None
    )
    if slot is None:
        raise BookingError("slot_taken", "That time isn't open.")

    customer = backend.find_customer_by_phone(phone)
    if customer is None:
        if not first_name:
            raise BookingError("name_required", "A first name is needed for a new client.")
        customer = backend.create_customer(phone, first_name, last_name)
    return backend.create_booking(slot, customer.id, note), customer
