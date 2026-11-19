"""The booking operations the agents rely on, implemented by the live and fake Square clients."""

from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from agent_service.square.models import Booking, Customer, Service, Slot


class BookingBackend(Protocol):
    tz: ZoneInfo

    def list_services(self) -> list[Service]: ...

    def find_availability(
        self,
        service: Service,
        start: datetime,
        end: datetime,
        team_member_id: str | None = None,
    ) -> list[Slot]: ...

    def create_booking(
        self, slot: Slot, customer_id: str, customer_note: str | None = None
    ) -> Booking: ...

    def find_customer_by_phone(self, phone: str) -> Customer | None: ...

    def create_customer(
        self, phone: str, given_name: str | None = None, family_name: str | None = None
    ) -> Customer: ...
