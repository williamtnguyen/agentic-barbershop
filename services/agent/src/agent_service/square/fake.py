"""In-memory stand-in for Square, for local chat and tests (SQUARE_MODE=fake).

It follows the same rules as the real client: slots fit inside opening hours, never
overlap existing bookings, never start in the past, and booking is idempotent.
"""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from agent_service.square.client import SquareError, normalize_phone
from agent_service.square.models import Booking, Customer, Service, Slot

TEAM_MEMBER = "TM_FAKE"

DEFAULT_SERVICES = [
    Service(
        name="Full Service",
        description="Scissor cut, clippers on the sides, straight razor line-up.",
        variation_id="SV_FULL",
        variation_version=1,
        duration_minutes=80,
        price_cents=4000,
        team_member_ids=[TEAM_MEMBER],
    ),
    Service(
        name="Clipper Cut",
        description="Clippers only, with a straight razor line-up.",
        variation_id="SV_CLIPPER",
        variation_version=1,
        duration_minutes=55,
        price_cents=3000,
        team_member_ids=[TEAM_MEMBER],
    ),
    Service(
        name="Beard Trim",
        description="Trim, straight razor edge-up, beard oil.",
        variation_id="SV_BEARD",
        variation_version=1,
        duration_minutes=15,
        price_cents=1000,
        team_member_ids=[TEAM_MEMBER],
    ),
]

# Weekday (Monday=0) -> opening windows in local time.
DEFAULT_HOURS: dict[int, list[tuple[time, time]]] = {
    3: [(time(12, 0), time(19, 0))],  # Thursday
    5: [(time(10, 0), time(16, 0))],  # Saturday
}

SLOT_STEP = timedelta(minutes=30)


class FakeSquareGateway:
    def __init__(
        self,
        tz: ZoneInfo,
        services: list[Service] | None = None,
        hours: dict[int, list[tuple[time, time]]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.tz = tz
        self.services = list(services or DEFAULT_SERVICES)
        self.hours = hours if hours is not None else DEFAULT_HOURS
        self._clock = clock or (lambda: datetime.now(UTC))
        self.bookings: list[Booking] = []
        self.customers: dict[str, Customer] = {}
        self._idempotency: dict[tuple[str, datetime, str], Booking] = {}

    # --- services and availability -----------------------------------------

    def list_services(self) -> list[Service]:
        return list(self.services)

    def _service(self, variation_id: str) -> Service:
        for service in self.services:
            if service.variation_id == variation_id:
                return service
        raise SquareError(f"unknown service variation {variation_id}")

    def _is_free(self, start: datetime, minutes: int) -> bool:
        end = start + timedelta(minutes=minutes)
        for booking in self.bookings:
            b_end = booking.start_at + timedelta(minutes=booking.duration_minutes or 0)
            if start < b_end and booking.start_at < end:
                return False
        return True

    def find_availability(
        self,
        service: Service,
        start: datetime,
        end: datetime,
        team_member_id: str | None = None,
    ) -> list[Slot]:
        if end <= start:
            raise ValueError("end must be after start")
        now = self._clock()
        duration = timedelta(minutes=service.duration_minutes)
        slots = []
        day = start.astimezone(self.tz).date()
        while datetime.combine(day, time.min, tzinfo=self.tz) < end:
            for open_at, close_at in self.hours.get(day.weekday(), []):
                t = datetime.combine(day, open_at, tzinfo=self.tz)
                close = datetime.combine(day, close_at, tzinfo=self.tz)
                while t + duration <= close:
                    if start <= t < end and t > now and self._is_free(t, service.duration_minutes):
                        slots.append(
                            Slot(
                                start_at=t.astimezone(UTC),
                                team_member_id=TEAM_MEMBER,
                                service_variation_id=service.variation_id,
                                service_variation_version=service.variation_version,
                                duration_minutes=service.duration_minutes,
                            )
                        )
                    t += SLOT_STEP
            day += timedelta(days=1)
        return slots

    # --- bookings -----------------------------------------------------------

    def create_booking(
        self, slot: Slot, customer_id: str, customer_note: str | None = None
    ) -> Booking:
        key = (customer_id, slot.start_at.astimezone(UTC), slot.service_variation_id)
        if key in self._idempotency:
            return self._idempotency[key]
        service = self._service(slot.service_variation_id)
        if not self._is_free(slot.start_at, service.duration_minutes):
            raise SquareError("That time is no longer available.")
        booking = Booking(
            id=f"BK_{len(self.bookings) + 1}",
            status="ACCEPTED",
            start_at=slot.start_at.astimezone(UTC),
            customer_id=customer_id,
            service_variation_id=service.variation_id,
            team_member_id=slot.team_member_id,
            duration_minutes=service.duration_minutes,
        )
        self.bookings.append(booking)
        self._idempotency[key] = booking
        return booking

    # --- customers ----------------------------------------------------------

    def find_customer_by_phone(self, phone: str) -> Customer | None:
        return self.customers.get(normalize_phone(phone))

    def create_customer(
        self, phone: str, given_name: str | None = None, family_name: str | None = None
    ) -> Customer:
        phone_number = normalize_phone(phone)
        if phone_number not in self.customers:
            self.customers[phone_number] = Customer(
                id=f"CU_{len(self.customers) + 1}",
                given_name=given_name,
                family_name=family_name,
                phone_number=phone_number,
            )
        return self.customers[phone_number]
