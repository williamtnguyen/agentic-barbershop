"""Small, agent-friendly views of Square objects."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel


class Service(BaseModel):
    name: str
    description: str | None = None
    variation_id: str
    variation_version: int
    duration_minutes: int
    price_cents: int | None = None
    team_member_ids: list[str] = []

    @property
    def price_display(self) -> str:
        return "price varies" if self.price_cents is None else f"${self.price_cents / 100:.2f}"


class Slot(BaseModel):
    """A bookable time returned by Square. `start_at` is kept exactly as Square gave it."""

    start_at: AwareDatetime
    team_member_id: str
    service_variation_id: str
    service_variation_version: int
    duration_minutes: int | None = None

    def local_start(self, tz: ZoneInfo) -> datetime:
        return self.start_at.astimezone(tz)


class Customer(BaseModel):
    id: str
    given_name: str | None = None
    family_name: str | None = None
    phone_number: str | None = None

    @property
    def display_name(self) -> str:
        return " ".join(n for n in (self.given_name, self.family_name) if n) or "client"


class Booking(BaseModel):
    id: str
    status: str | None = None
    start_at: AwareDatetime
    customer_id: str | None = None
    service_variation_id: str | None = None
    team_member_id: str | None = None
    duration_minutes: int | None = None
