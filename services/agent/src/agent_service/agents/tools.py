"""Front desk tools. Plain functions over a BookingBackend, wrapped for Strands.

Tools return small dicts. Problems come back as {"error": ...} so the agent can explain
or recover instead of crashing the conversation.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from strands import tool

from agent_service.square.backend import BookingBackend
from agent_service.square.client import SquareError
from agent_service.square.models import Service
from agent_service.square.times import day_range

MAX_SEARCH_DAYS = 14
MAX_SLOTS_RETURNED = 40


def _label(dt: datetime) -> str:
    return dt.strftime("%a %b %-d, %-I:%M %p")


def resolve_service(services: list[Service], name: str) -> Service | str:
    """Match a service by name. Returns the service, or an error message."""
    wanted = name.strip().lower()
    exact = [s for s in services if s.name.lower() == wanted]
    if exact:
        return exact[0]
    partial = [s for s in services if wanted in s.name.lower() or s.name.lower() in wanted]
    if len(partial) == 1:
        return partial[0]
    options = ", ".join(s.name for s in services)
    if partial:
        return f"'{name}' matches more than one service. Options: {options}"
    return f"No service called '{name}'. Options: {options}"


def build_tools(backend: BookingBackend, clock: Callable[[], datetime] | None = None) -> list[Any]:
    tz = backend.tz
    now = clock or (lambda: datetime.now(UTC))

    @tool
    def list_services() -> list[dict]:
        """List the services clients can book, with length and price."""
        return [
            {
                "name": s.name,
                "minutes": s.duration_minutes,
                "price": s.price_display,
                "description": s.description,
            }
            for s in backend.list_services()
        ]

    @tool
    def find_open_slots(service: str, start_date: str, end_date: str | None = None) -> dict:
        """Find open appointment times for a service.

        Args:
            service: Service name, e.g. "Clipper Cut".
            start_date: First day to search, YYYY-MM-DD in the shop's local time.
            end_date: Last day to search (inclusive), YYYY-MM-DD. Defaults to start_date.
                At most 14 days after start_date.
        """
        found = resolve_service(backend.list_services(), service)
        if isinstance(found, str):
            return {"error": found}
        try:
            first = date.fromisoformat(start_date)
            last = date.fromisoformat(end_date) if end_date else first
        except ValueError:
            return {"error": "Dates must be YYYY-MM-DD."}
        if last < first:
            return {"error": "end_date is before start_date."}
        if (last - first).days >= MAX_SEARCH_DAYS:
            return {"error": f"Search at most {MAX_SEARCH_DAYS} days at a time."}

        start = max(day_range(first, tz)[0], now().astimezone(tz))
        end = day_range(last, tz)[1]
        if end <= start:
            return {"service": found.name, "slots": [], "note": "Those dates are in the past."}
        try:
            slots = backend.find_availability(found, start, end)
        except (SquareError, ValueError) as error:
            return {"error": str(error)}
        return {
            "service": found.name,
            "minutes": found.duration_minutes,
            "slots": [
                {
                    "start": s.local_start(tz).strftime("%Y-%m-%dT%H:%M"),
                    "label": _label(s.local_start(tz)),
                }
                for s in slots[:MAX_SLOTS_RETURNED]
            ],
            "truncated": len(slots) > MAX_SLOTS_RETURNED,
        }

    @tool
    def lookup_client(phone: str) -> dict:
        """Look up a client by phone number.

        Args:
            phone: The client's phone number.
        """
        try:
            customer = backend.find_customer_by_phone(phone)
        except (SquareError, ValueError) as error:
            return {"error": str(error)}
        if customer is None:
            return {"found": False}
        return {"found": True, "name": customer.display_name}

    @tool
    def book_appointment(
        service: str,
        start: str,
        phone: str,
        first_name: str | None = None,
        last_name: str | None = None,
        note: str | None = None,
    ) -> dict:
        """Book an appointment. Only call this after the client has confirmed the details.

        Args:
            service: Service name, e.g. "Full Service".
            start: Start time exactly as returned by find_open_slots, YYYY-MM-DDTHH:MM local.
            phone: The client's phone number.
            first_name: Required for a new client; optional for a returning one.
            last_name: Optional.
            note: Optional note for the barber, e.g. "low fade, keep length on top".
        """
        found = resolve_service(backend.list_services(), service)
        if isinstance(found, str):
            return {"error": found}
        try:
            parsed = datetime.fromisoformat(start)
            wanted = parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
        except ValueError:
            return {"error": "start must be YYYY-MM-DDTHH:MM, as returned by find_open_slots."}

        try:
            day_start, day_end = day_range(wanted.date(), tz)
            slots = backend.find_availability(found, max(day_start, now()), day_end)
            slot = next((s for s in slots if s.start_at == wanted), None)
            if slot is None:
                return {"error": "That time isn't open. Check find_open_slots again."}

            customer = backend.find_customer_by_phone(phone)
            if customer is None:
                if not first_name:
                    return {"error": "New client: ask for their first name before booking."}
                customer = backend.create_customer(phone, first_name, last_name)
            booking = backend.create_booking(slot, customer.id, note)
        except (SquareError, ValueError) as error:
            return {"error": str(error)}

        return {
            "booked": True,
            "booking_id": booking.id,
            "service": found.name,
            "when": _label(booking.start_at.astimezone(tz)),
            "client": customer.display_name,
        }

    return [list_services, find_open_slots, lookup_client, book_appointment]
