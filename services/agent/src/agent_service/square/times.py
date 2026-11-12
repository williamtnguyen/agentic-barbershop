"""Time conversion between the business timezone and Square.

Square sends and receives RFC 3339 timestamps. We always send UTC and refuse naive
datetimes, so a wall-clock time can never be mistaken for UTC.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def to_square_time(dt: datetime) -> str:
    """Format an aware datetime as a UTC RFC 3339 string for Square."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive datetime: attach a timezone before sending to Square")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_square_time(value: str) -> datetime:
    """Parse a Square RFC 3339 timestamp into an aware UTC datetime."""
    return datetime.fromisoformat(value).astimezone(UTC)


def day_range(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Start and end of a calendar day in the business timezone, as aware datetimes."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
