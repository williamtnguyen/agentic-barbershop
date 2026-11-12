"""Read-only check against Square: lists services and the next open slots.

    uv run --package agent-service python -m agent_service.square.smoke

Reads SQUARE_* and BUSINESS_TIMEZONE from the environment or .env. Never books anything.
"""

from datetime import datetime, timedelta

from agent_service.settings import get_settings
from agent_service.square import SquareGateway


def main() -> None:
    settings = get_settings()
    gateway = SquareGateway.from_settings(settings)
    print(f"Square {settings.square_environment}, location {settings.square_location_id}")

    services = gateway.list_services()
    for service in services:
        print(f"- {service.name}: {service.duration_minutes} min, {service.price_display}")
    if not services:
        print("No bookable services found.")
        return

    start = datetime.now(settings.tz) + timedelta(hours=1)
    slots = gateway.find_availability(services[0], start, start + timedelta(days=7))
    print(f"\nNext open slots for {services[0].name}:")
    for slot in slots[:5]:
        print(f"  {slot.local_start(settings.tz):%a %b %d, %I:%M %p}")
    if not slots:
        print("  none in the next 7 days")


if __name__ == "__main__":
    main()
