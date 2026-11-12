from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from square.core.api_error import ApiError
from square.types.appointment_segment import AppointmentSegment
from square.types.availability import Availability
from square.types.booking import Booking as SquareBooking
from square.types.catalog_item import CatalogItem
from square.types.catalog_item_variation import CatalogItemVariation
from square.types.catalog_object import CatalogObject_Item, CatalogObject_ItemVariation
from square.types.create_booking_response import CreateBookingResponse
from square.types.customer import Customer as SquareCustomer
from square.types.money import Money
from square.types.search_availability_response import SearchAvailabilityResponse
from square.types.search_catalog_items_response import SearchCatalogItemsResponse
from square.types.search_customers_response import SearchCustomersResponse

from agent_service.square import Service, Slot, SquareError, SquareGateway, normalize_phone

LA = ZoneInfo("America/Los_Angeles")
LOCATION = "LOC1"


def make_gateway() -> tuple[SquareGateway, MagicMock]:
    client = MagicMock()
    return SquareGateway(client, LOCATION, LA), client


def variation(vid, name, minutes, cents, bookable=True):
    return CatalogObject_ItemVariation(
        type="ITEM_VARIATION",
        id=vid,
        version=7,
        item_variation_data=CatalogItemVariation(
            name=name,
            service_duration=minutes * 60_000,
            price_money=Money(amount=cents, currency="USD"),
            team_member_ids=["TM1"],
            available_for_booking=bookable,
        ),
    )


def item(iid, name, variations):
    return CatalogObject_Item(
        type="ITEM", id=iid, item_data=CatalogItem(name=name, variations=variations)
    )


SERVICE = Service(name="Cut", variation_id="V1", variation_version=7, duration_minutes=55)


# --- services ---------------------------------------------------------------


def test_list_services_maps_fields_and_follows_pages():
    gateway, client = make_gateway()
    client.catalog.search_items.side_effect = [
        SearchCatalogItemsResponse(
            items=[item("I1", "Full Service", [variation("V1", "Regular", 80, 4000)])],
            cursor="next",
        ),
        SearchCatalogItemsResponse(
            items=[
                item(
                    "I2",
                    "Beard",
                    [
                        variation("V2", "Trim", 15, 1000),
                        variation("V3", "Shape", 20, 1500),
                        variation("V4", "Hidden", 5, 500, bookable=False),
                    ],
                )
            ]
        ),
    ]

    services = gateway.list_services()

    assert [s.name for s in services] == ["Full Service", "Beard (Trim)", "Beard (Shape)"]
    full = services[0]
    assert (full.variation_id, full.variation_version) == ("V1", 7)
    assert (full.duration_minutes, full.price_cents, full.price_display) == (80, 4000, "$40.00")
    first_call, second_call = client.catalog.search_items.call_args_list
    assert first_call.kwargs["product_types"] == ["APPOINTMENTS_SERVICE"]
    assert first_call.kwargs["enabled_location_ids"] == [LOCATION]
    assert "cursor" not in first_call.kwargs
    assert second_call.kwargs["cursor"] == "next"


# --- availability -----------------------------------------------------------


def availability(start_at: str) -> Availability:
    return Availability(
        start_at=start_at,
        location_id=LOCATION,
        appointment_segments=[
            AppointmentSegment(
                team_member_id="TM1",
                service_variation_id="V1",
                service_variation_version=9,
                duration_minutes=55,
            )
        ],
    )


def test_find_availability_sends_utc_and_returns_slots_in_window():
    gateway, client = make_gateway()
    client.bookings.search_availability.return_value = SearchAvailabilityResponse(
        availabilities=[
            availability("2026-11-14T19:00:00Z"),  # 11:00am local, inside
            availability("2026-11-14T22:30:00Z"),  # 2:30pm local, inside
            availability("2026-11-15T19:00:00Z"),  # next day, outside requested window
        ]
    )
    start = datetime(2026, 11, 14, 9, 0, tzinfo=LA)
    end = datetime(2026, 11, 14, 18, 0, tzinfo=LA)

    slots = gateway.find_availability(SERVICE, start, end, team_member_id="TM1")

    query = client.bookings.search_availability.call_args.kwargs["query"]["filter"]
    assert query["start_at_range"]["start_at"] == "2026-11-14T17:00:00Z"
    # Short windows are widened to Square's 24-hour minimum, then filtered locally.
    assert query["start_at_range"]["end_at"] == "2026-11-15T17:00:00Z"
    assert query["location_id"] == LOCATION
    assert query["segment_filters"] == [
        {"service_variation_id": "V1", "team_member_id_filter": {"any": ["TM1"]}}
    ]
    assert [s.local_start(LA).strftime("%H:%M") for s in slots] == ["11:00", "14:30"]
    assert slots[0].service_variation_version == 9


@pytest.mark.parametrize("days", [0, 32])
def test_find_availability_rejects_bad_windows(days):
    gateway, _ = make_gateway()
    start = datetime(2026, 11, 14, 9, 0, tzinfo=LA)
    with pytest.raises(ValueError):
        gateway.find_availability(SERVICE, start, start + timedelta(days=days))


# --- booking ----------------------------------------------------------------


def booking_response(start_at: str) -> CreateBookingResponse:
    return CreateBookingResponse(
        booking=SquareBooking(
            id="B1",
            status="ACCEPTED",
            start_at=start_at,
            customer_id="C1",
            appointment_segments=[
                AppointmentSegment(
                    team_member_id="TM1", service_variation_id="V1", duration_minutes=55
                )
            ],
        )
    )


def test_create_booking_sends_the_slots_exact_utc_time():
    # Regression for the prototype bug: 2:30pm local was sent to Square as 14:30 UTC.
    gateway, client = make_gateway()
    client.bookings.create.return_value = booking_response("2026-11-14T22:30:00Z")
    slot = Slot(
        start_at=datetime(2026, 11, 14, 14, 30, tzinfo=LA),
        team_member_id="TM1",
        service_variation_id="V1",
        service_variation_version=9,
    )

    booking = gateway.create_booking(slot, customer_id="C1", customer_note="skin fade")

    sent = client.bookings.create.call_args.kwargs["booking"]
    assert sent["start_at"] == "2026-11-14T22:30:00Z"
    assert sent["location_id"] == LOCATION
    assert sent["customer_note"] == "skin fade"
    assert sent["appointment_segments"] == [
        {"team_member_id": "TM1", "service_variation_id": "V1", "service_variation_version": 9}
    ]
    assert booking.id == "B1"
    assert booking.start_at.astimezone(LA).strftime("%H:%M") == "14:30"


def test_create_booking_retries_reuse_the_idempotency_key():
    gateway, client = make_gateway()
    client.bookings.create.return_value = booking_response("2026-11-14T22:30:00Z")
    slot = Slot(
        start_at=datetime(2026, 11, 14, 14, 30, tzinfo=LA),
        team_member_id="TM1",
        service_variation_id="V1",
        service_variation_version=9,
    )
    later = slot.model_copy(update={"start_at": slot.start_at + timedelta(hours=1)})

    gateway.create_booking(slot, customer_id="C1")
    gateway.create_booking(slot, customer_id="C1")
    gateway.create_booking(later, customer_id="C1")

    keys = [c.kwargs["idempotency_key"] for c in client.bookings.create.call_args_list]
    assert keys[0] == keys[1]
    assert keys[2] != keys[0]


# --- customers --------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["(408) 555-0123", "408-555-0123", "4085550123", "+1 408 555 0123", "1-408-555-0123"],
)
def test_normalize_phone_us_formats(raw):
    assert normalize_phone(raw) == "+14085550123"


def test_normalize_phone_rejects_garbage():
    with pytest.raises(ValueError):
        normalize_phone("555-0123")


def test_find_customer_by_phone_uses_e164():
    gateway, client = make_gateway()
    client.customers.search.return_value = SearchCustomersResponse(
        customers=[SquareCustomer(id="C1", given_name="Sam", phone_number="+14085550123")]
    )

    customer = gateway.find_customer_by_phone("(408) 555-0123")

    query = client.customers.search.call_args.kwargs["query"]
    assert query == {"filter": {"phone_number": {"exact": "+14085550123"}}}
    assert (customer.id, customer.display_name) == ("C1", "Sam")


def test_find_customer_by_phone_returns_none_when_missing():
    gateway, client = make_gateway()
    client.customers.search.return_value = SearchCustomersResponse(customers=None)
    assert gateway.find_customer_by_phone("4085550123") is None


# --- errors -----------------------------------------------------------------


def test_api_errors_become_square_errors_with_detail():
    gateway, client = make_gateway()
    client.bookings.search_availability.side_effect = ApiError(
        status_code=400,
        body={"errors": [{"code": "BAD_REQUEST", "detail": "Invalid start_at_range"}]},
    )
    start = datetime(2026, 11, 14, 9, 0, tzinfo=LA)

    with pytest.raises(SquareError, match="Invalid start_at_range"):
        gateway.find_availability(SERVICE, start, start + timedelta(days=1))
