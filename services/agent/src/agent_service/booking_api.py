"""Booking API for the web app's calendar: services, open days and times, and booking."""

import calendar
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from agent_service.booking import BookingError, Clock, book, open_slots, parse_local_time
from agent_service.square.backend import BookingBackend
from agent_service.square.client import SquareError, normalize_phone
from agent_service.square.models import Service

logger = logging.getLogger(__name__)
router = APIRouter()

SQUARE_DOWN = "Booking is unavailable right now. Try again in a moment."
API_MESSAGES = {
    "slot_taken": "That time was just taken. Pick another time.",
    "name_required": "Add your first name to book.",
    "bad_time": "That time isn't valid. Pick a time from the list.",
}


def get_backend(request: Request) -> BookingBackend:
    return request.app.state.get_backend()


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


Backend = Annotated[BookingBackend, Depends(get_backend)]
Now = Annotated[Clock, Depends(get_clock)]


class ServiceOut(BaseModel):
    id: str
    name: str
    minutes: int
    price: str
    description: str | None = None


class TimeSlot(BaseModel):
    start: str  # YYYY-MM-DDTHH:MM, shop-local
    label: str


class OpenTimes(BaseModel):
    service_id: str
    date: date
    slots: list[TimeSlot]


class OpenDays(BaseModel):
    service_id: str
    month: str
    days: list[date]


class BookingRequest(BaseModel):
    service_id: str = Field(min_length=1)
    start: str = Field(min_length=1)
    phone: str
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("first_name", "last_name", "note")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class BookingOut(BaseModel):
    booking_id: str
    service: str
    start: str
    when: str
    client: str


def _service(backend: BookingBackend, service_id: str) -> Service:
    try:
        services = backend.list_services()
    except SquareError as error:
        logger.exception("listing services failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SQUARE_DOWN) from error
    for service in services:
        if service.variation_id == service_id:
            return service
    raise HTTPException(status.HTTP_404_NOT_FOUND, "That service isn't available.")


def _time_label(slot_start) -> str:
    return slot_start.strftime("%-I:%M %p")


@router.get("/services")
def list_services(backend: Backend) -> list[ServiceOut]:
    try:
        services = backend.list_services()
    except SquareError as error:
        logger.exception("listing services failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SQUARE_DOWN) from error
    return [
        ServiceOut(
            id=s.variation_id,
            name=s.name,
            minutes=s.duration_minutes,
            price=s.price_display,
            description=s.description,
        )
        for s in services
    ]


@router.get("/availability/days")
def open_days(
    backend: Backend,
    now: Now,
    service_id: str,
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> OpenDays:
    """Days in a month (YYYY-MM) that have at least one open time."""
    service = _service(backend, service_id)
    try:
        year, mon = (int(part) for part in month.split("-"))
        first = date(year, mon, 1)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid month.") from error
    last = date(year, mon, calendar.monthrange(year, mon)[1])
    try:
        slots = open_slots(backend, service, first, last, now)
    except SquareError as error:
        logger.exception("availability failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SQUARE_DOWN) from error
    days = sorted({s.local_start(backend.tz).date() for s in slots})
    return OpenDays(service_id=service_id, month=month, days=days)


@router.get("/availability")
def open_times(backend: Backend, now: Now, service_id: str, date: date) -> OpenTimes:
    """Open start times for a service on one day."""
    service = _service(backend, service_id)
    try:
        slots = open_slots(backend, service, date, date, now)
    except SquareError as error:
        logger.exception("availability failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SQUARE_DOWN) from error
    tz = backend.tz
    return OpenTimes(
        service_id=service_id,
        date=date,
        slots=[
            TimeSlot(
                start=s.local_start(tz).strftime("%Y-%m-%dT%H:%M"),
                label=_time_label(s.local_start(tz)),
            )
            for s in slots
        ],
    )


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(body: BookingRequest, backend: Backend, now: Now) -> BookingOut:
    service = _service(backend, body.service_id)
    try:
        start = parse_local_time(body.start, backend)
        booking, customer = book(
            backend,
            service,
            start,
            body.phone,
            body.first_name,
            body.last_name,
            body.note,
            now=now,
        )
    except BookingError as error:
        code = (
            status.HTTP_409_CONFLICT
            if error.code == "slot_taken"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(code, API_MESSAGES[error.code]) from error
    except SquareError as error:
        logger.exception("booking failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SQUARE_DOWN) from error

    local = booking.start_at.astimezone(backend.tz)
    return BookingOut(
        booking_id=booking.id,
        service=service.name,
        start=local.strftime("%Y-%m-%dT%H:%M"),
        when=local.strftime("%A, %B %-d at %-I:%M %p"),
        client=customer.display_name,
    )
