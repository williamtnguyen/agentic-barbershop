import pytest

from agent_service.agents.tools import build_tools, resolve_service
from agent_service.square.fake import DEFAULT_SERVICES


@pytest.fixture
def tools(fake_square, clock):
    return {t.tool_name: t for t in build_tools(fake_square, clock=clock)}


def test_list_services(tools):
    services = tools["list_services"]()
    assert [s["name"] for s in services] == ["Full Service", "Clipper Cut", "Beard Trim"]
    assert services[0]["price"] == "$40.00"


def test_find_open_slots_returns_local_times(tools):
    result = tools["find_open_slots"]("clipper", "2026-11-19")
    assert result["service"] == "Clipper Cut"
    assert result["slots"][0] == {"start": "2026-11-19T12:00", "label": "Thu Nov 19, 12:00 PM"}


def test_find_open_slots_spans_days_and_skips_closed_ones(tools):
    result = tools["find_open_slots"]("Beard Trim", "2026-11-19", "2026-11-21")
    days = {s["start"][:10] for s in result["slots"]}
    assert days == {"2026-11-19", "2026-11-21"}  # Friday is closed


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("perm", "2026-11-19"), "No service called"),
        (("clipper", "Thursday"), "YYYY-MM-DD"),
        (("clipper", "2026-11-19", "2026-12-19"), "at most 14 days"),
        (("clipper", "2026-11-19", "2026-11-18"), "before start_date"),
    ],
)
def test_find_open_slots_errors(tools, args, message):
    assert message in tools["find_open_slots"](*args)["error"]


def test_resolve_service_flags_ambiguous_names():
    result = resolve_service(DEFAULT_SERVICES, "r")
    assert isinstance(result, str) and "more than one" in result


def test_new_client_needs_a_first_name(tools, fake_square):
    result = tools["book_appointment"]("Clipper Cut", "2026-11-19T12:00", "4085550123")
    assert "first name" in result["error"]
    assert fake_square.bookings == []


def test_book_appointment_creates_client_and_booking(tools, fake_square):
    result = tools["book_appointment"](
        "Clipper Cut", "2026-11-19T12:00", "4085550123", first_name="Sam", note="low fade"
    )

    assert result == {
        "booked": True,
        "booking_id": "BK_1",
        "service": "Clipper Cut",
        "when": "Thu Nov 19, 12:00 PM",
        "client": "Sam",
    }
    assert tools["lookup_client"]("408-555-0123") == {"found": True, "name": "Sam"}
    remaining = tools["find_open_slots"]("Clipper Cut", "2026-11-19")["slots"]
    assert remaining[0]["start"] == "2026-11-19T13:00"


def test_repeated_booking_call_does_not_double_book(tools, fake_square):
    args = ("Clipper Cut", "2026-11-19T12:00", "4085550123")
    tools["book_appointment"](*args, first_name="Sam")
    tools["book_appointment"](*args)
    assert len(fake_square.bookings) == 1


@pytest.mark.parametrize("start", ["2026-11-20T12:00", "2026-11-19T12:10", "tomorrow at noon"])
def test_book_appointment_rejects_times_that_are_not_open(tools, start):
    result = tools["book_appointment"]("Clipper Cut", start, "4085550123", first_name="Sam")
    assert "error" in result


def test_lookup_unknown_client(tools):
    assert tools["lookup_client"]("4085550199") == {"found": False}
