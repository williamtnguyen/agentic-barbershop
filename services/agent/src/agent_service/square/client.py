"""Thin wrapper around the Square SDK for the agents.

Only buyer-level operations are used, so this works on the Square Appointments Free plan.
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from square import Square
from square.core.api_error import ApiError
from square.environment import SquareEnvironment

from agent_service.settings import Settings
from agent_service.square.models import Booking, Customer, Service, Slot
from agent_service.square.times import from_square_time, to_square_time

# Square requires availability searches to span at least 24 hours and at most 32 days.
MIN_SEARCH_WINDOW = timedelta(hours=24)
MAX_SEARCH_WINDOW = timedelta(days=31)

_BOOKING_NAMESPACE = uuid.UUID("6f1c2a3e-7d5b-4c8e-9a0f-2b3c4d5e6f70")


class SquareError(Exception):
    """A Square API call failed. The message is safe to show an agent."""


def normalize_phone(phone: str) -> str:
    """Normalize a US phone number to E.164 (+1XXXXXXXXXX)."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if phone.strip().startswith("+") and 8 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValueError(f"not a valid phone number: {phone!r}")


def _error_message(error: ApiError) -> str:
    body = error.body if isinstance(error.body, dict) else {}
    details = [e.get("detail") or e.get("code") for e in body.get("errors", [])]
    return "; ".join(d for d in details if d) or f"Square API error (HTTP {error.status_code})"


class SquareGateway:
    def __init__(self, client: Any, location_id: str, tz: ZoneInfo):
        self._client = client
        self.location_id = location_id
        self.tz = tz

    @classmethod
    def from_settings(cls, settings: Settings) -> "SquareGateway":
        environment = (
            SquareEnvironment.PRODUCTION
            if settings.square_environment == "production"
            else SquareEnvironment.SANDBOX
        )
        client = Square(token=settings.square_access_token, environment=environment)
        return cls(client, settings.square_location_id, settings.tz)

    def list_services(self) -> list[Service]:
        """Bookable appointment services at this location."""
        services: list[Service] = []
        cursor = None
        while True:
            try:
                response = self._client.catalog.search_items(
                    product_types=["APPOINTMENTS_SERVICE"],
                    enabled_location_ids=[self.location_id],
                    **({"cursor": cursor} if cursor else {}),
                )
            except ApiError as error:
                raise SquareError(_error_message(error)) from error
            for item in response.items or []:
                services.extend(self._services_from_item(item))
            cursor = response.cursor
            if not cursor:
                return services

    @staticmethod
    def _services_from_item(item: Any) -> list[Service]:
        data = item.item_data
        variations = [
            v
            for v in (data.variations or [])
            if v.item_variation_data and v.item_variation_data.available_for_booking is not False
        ]
        services = []
        for variation in variations:
            vdata = variation.item_variation_data
            name = data.name or "Service"
            if len(variations) > 1 and vdata.name:
                name = f"{name} ({vdata.name})"
            services.append(
                Service(
                    name=name,
                    description=data.description,
                    variation_id=variation.id,
                    variation_version=variation.version,
                    duration_minutes=(vdata.service_duration or 0) // 60_000,
                    price_cents=vdata.price_money.amount if vdata.price_money else None,
                    team_member_ids=vdata.team_member_ids or [],
                )
            )
        return services

    def find_availability(
        self,
        service: Service,
        start: datetime,
        end: datetime,
        team_member_id: str | None = None,
    ) -> list[Slot]:
        """Open slots for a service that start within [start, end)."""
        if end <= start:
            raise ValueError("end must be after start")
        if end - start > MAX_SEARCH_WINDOW:
            raise ValueError("search window is limited to 31 days")
        query_end = max(end, start + MIN_SEARCH_WINDOW)

        segment_filter: dict[str, Any] = {"service_variation_id": service.variation_id}
        if team_member_id:
            segment_filter["team_member_id_filter"] = {"any": [team_member_id]}
        query = {
            "filter": {
                "start_at_range": {
                    "start_at": to_square_time(start),
                    "end_at": to_square_time(query_end),
                },
                "location_id": self.location_id,
                "segment_filters": [segment_filter],
            }
        }
        try:
            response = self._client.bookings.search_availability(query=query)
        except ApiError as error:
            raise SquareError(_error_message(error)) from error

        slots = []
        for availability in response.availabilities or []:
            segment = (availability.appointment_segments or [None])[0]
            if not availability.start_at or segment is None:
                continue
            slot_start = from_square_time(availability.start_at)
            if not start <= slot_start < end:
                continue
            slots.append(
                Slot(
                    start_at=slot_start,
                    team_member_id=segment.team_member_id,
                    service_variation_id=segment.service_variation_id or service.variation_id,
                    service_variation_version=(
                        segment.service_variation_version or service.variation_version
                    ),
                    duration_minutes=segment.duration_minutes,
                )
            )
        return slots

    def create_booking(
        self, slot: Slot, customer_id: str, customer_note: str | None = None
    ) -> Booking:
        """Book a slot for a customer.

        The idempotency key is derived from the customer, time and service, so a retried
        call (for example an agent repeating a tool call) cannot create a second booking.
        """
        start_at = to_square_time(slot.start_at)
        key = uuid.uuid5(
            _BOOKING_NAMESPACE, f"{customer_id}|{start_at}|{slot.service_variation_id}"
        )
        booking: dict[str, Any] = {
            "location_id": self.location_id,
            "start_at": start_at,
            "customer_id": customer_id,
            "appointment_segments": [
                {
                    "team_member_id": slot.team_member_id,
                    "service_variation_id": slot.service_variation_id,
                    "service_variation_version": slot.service_variation_version,
                }
            ],
        }
        if customer_note:
            booking["customer_note"] = customer_note
        try:
            response = self._client.bookings.create(booking=booking, idempotency_key=str(key))
        except ApiError as error:
            raise SquareError(_error_message(error)) from error
        return self._booking_from_square(response.booking)

    @staticmethod
    def _booking_from_square(booking: Any) -> Booking:
        segment = (booking.appointment_segments or [None])[0]
        return Booking(
            id=booking.id,
            status=booking.status,
            start_at=from_square_time(booking.start_at),
            customer_id=booking.customer_id,
            service_variation_id=segment.service_variation_id if segment else None,
            team_member_id=segment.team_member_id if segment else None,
            duration_minutes=segment.duration_minutes if segment else None,
        )

    def find_customer_by_phone(self, phone: str) -> Customer | None:
        try:
            response = self._client.customers.search(
                query={"filter": {"phone_number": {"exact": normalize_phone(phone)}}},
                limit=1,
            )
        except ApiError as error:
            raise SquareError(_error_message(error)) from error
        customers = response.customers or []
        return self._customer_from_square(customers[0]) if customers else None

    def create_customer(
        self, phone: str, given_name: str | None = None, family_name: str | None = None
    ) -> Customer:
        phone_number = normalize_phone(phone)
        try:
            names = {"given_name": given_name, "family_name": family_name}
            response = self._client.customers.create(
                idempotency_key=str(uuid.uuid5(_BOOKING_NAMESPACE, f"customer|{phone_number}")),
                phone_number=phone_number,
                **{k: v for k, v in names.items() if v},
            )
        except ApiError as error:
            raise SquareError(_error_message(error)) from error
        return self._customer_from_square(response.customer)

    @staticmethod
    def _customer_from_square(customer: Any) -> Customer:
        return Customer(
            id=customer.id,
            given_name=customer.given_name,
            family_name=customer.family_name,
            phone_number=customer.phone_number,
        )
