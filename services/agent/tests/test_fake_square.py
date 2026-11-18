from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from agent_service.square import SquareError
from agent_service.square.fake import FakeSquareGateway

LA = ZoneInfo("America/Los_Angeles")
THURSDAY = datetime(2026, 11, 19, 0, 0, tzinfo=LA)


def service(gateway, name):
    return next(s for s in gateway.list_services() if s.name == name)


def local_times(slots):
    return [s.local_start(LA).strftime("%H:%M") for s in slots]


def test_slots_fit_inside_opening_hours(fake_square):
    clipper = service(fake_square, "Clipper Cut")  # 55 minutes; Thursday 12:00-19:00
    times = local_times(fake_square.find_availability(clipper, THURSDAY, THURSDAY + timedelta(1)))
    assert times[0] == "12:00"
    assert times[-1] == "18:00"  # 18:30 + 55 min would run past close
    assert len(times) == 13


def test_closed_days_have_no_slots(fake_square):
    friday = THURSDAY + timedelta(days=1)
    assert (
        fake_square.find_availability(
            service(fake_square, "Beard Trim"), friday, friday + timedelta(1)
        )
        == []
    )


def test_bookings_block_overlapping_slots(fake_square):
    full = service(fake_square, "Full Service")  # 80 minutes
    first = fake_square.find_availability(full, THURSDAY, THURSDAY + timedelta(1))[0]
    fake_square.create_booking(first, "CU_1")  # 12:00-13:20

    clipper = service(fake_square, "Clipper Cut")
    times = local_times(fake_square.find_availability(clipper, THURSDAY, THURSDAY + timedelta(1)))
    assert times[0] == "13:30"


def test_past_times_are_never_offered():
    thursday_afternoon = datetime(2026, 11, 19, 15, 10, tzinfo=LA)
    gateway = FakeSquareGateway(LA, clock=lambda: thursday_afternoon)
    beard = service(gateway, "Beard Trim")
    times = local_times(gateway.find_availability(beard, THURSDAY, THURSDAY + timedelta(1)))
    assert times[0] == "15:30"


def test_booking_is_idempotent_and_rejects_conflicts(fake_square):
    clipper = service(fake_square, "Clipper Cut")
    slot = fake_square.find_availability(clipper, THURSDAY, THURSDAY + timedelta(1))[0]

    first = fake_square.create_booking(slot, "CU_1")
    again = fake_square.create_booking(slot, "CU_1")
    assert first.id == again.id
    assert len(fake_square.bookings) == 1

    with pytest.raises(SquareError, match="no longer available"):
        fake_square.create_booking(slot, "CU_2")


def test_customers_are_keyed_by_normalized_phone(fake_square):
    created = fake_square.create_customer("(408) 555-0123", "Sam")
    assert fake_square.find_customer_by_phone("408-555-0123") == created
    assert fake_square.find_customer_by_phone("4085550199") is None
