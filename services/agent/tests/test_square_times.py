from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from agent_service.square.times import day_range, from_square_time, to_square_time

LA = ZoneInfo("America/Los_Angeles")


def test_standard_time_local_slot_is_sent_as_utc():
    # 2:30pm in November (PST, UTC-8) is 22:30 UTC, not 14:30 UTC.
    assert to_square_time(datetime(2026, 11, 14, 14, 30, tzinfo=LA)) == "2026-11-14T22:30:00Z"


def test_daylight_time_local_slot_is_sent_as_utc():
    # 2:30pm in July (PDT, UTC-7) is 21:30 UTC.
    assert to_square_time(datetime(2026, 7, 11, 14, 30, tzinfo=LA)) == "2026-07-11T21:30:00Z"


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError, match="naive"):
        to_square_time(datetime(2026, 11, 14, 14, 30))


@pytest.mark.parametrize("value", ["2026-11-14T22:30:00Z", "2026-11-14T22:30:00+00:00"])
def test_square_timestamps_parse_to_aware_utc(value):
    parsed = from_square_time(value)
    assert parsed == datetime(2026, 11, 14, 22, 30, tzinfo=UTC)
    assert parsed.astimezone(LA).hour == 14


def test_day_range_handles_daylight_saving_end():
    start, end = day_range(date(2026, 11, 1), LA)  # clocks fall back this day
    # Same-zone subtraction is wall-clock in Python; compare real instants instead.
    assert (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds() == 25 * 3600
    assert to_square_time(start) == "2026-11-01T07:00:00Z"
    assert to_square_time(end) == "2026-11-02T08:00:00Z"
