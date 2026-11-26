from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from agent_service.app import create_app
from agent_service.conversations import ConversationStore
from agent_service.square import SquareError

BOOKING = {
    "service_id": "SV_CLIPPER",
    "start": "2026-11-19T12:00",
    "phone": "(408) 555-0123",
    "first_name": "Sam",
}


@pytest.fixture
def client(fake_square, clock):
    return TestClient(create_app(backend=fake_square, clock=clock))


def test_lists_services(client):
    services = client.get("/services").json()
    assert [s["id"] for s in services] == ["SV_FULL", "SV_CLIPPER", "SV_BEARD"]
    assert services[1] == {
        "id": "SV_CLIPPER",
        "name": "Clipper Cut",
        "minutes": 55,
        "price": "$30.00",
        "description": "Clippers only, with a straight razor line-up.",
    }


def test_open_days_in_a_month(client):
    response = client.get(
        "/availability/days", params={"service_id": "SV_CLIPPER", "month": "2026-11"}
    )
    days = response.json()["days"]
    # Today is Wed Nov 18; the shop opens Thursdays and Saturdays.
    assert days == ["2026-11-19", "2026-11-21", "2026-11-26", "2026-11-28"]


def test_open_days_for_a_past_month_is_empty(client):
    response = client.get(
        "/availability/days", params={"service_id": "SV_CLIPPER", "month": "2026-10"}
    )
    assert response.json()["days"] == []


def test_open_times_on_a_day(client):
    body = client.get(
        "/availability", params={"service_id": "SV_BEARD", "date": "2026-11-21"}
    ).json()
    assert body["slots"][0] == {"start": "2026-11-21T10:00", "label": "10:00 AM"}
    assert body["slots"][-1] == {"start": "2026-11-21T15:30", "label": "3:30 PM"}


def test_closed_day_has_no_times(client):
    body = client.get(
        "/availability", params={"service_id": "SV_BEARD", "date": "2026-11-20"}
    ).json()
    assert body["slots"] == []


def test_books_and_removes_the_time(client, fake_square):
    response = client.post("/bookings", json=BOOKING | {"note": "  low fade  "})

    assert response.status_code == 201
    assert response.json() == {
        "booking_id": "BK_1",
        "service": "Clipper Cut",
        "start": "2026-11-19T12:00",
        "when": "Thursday, November 19 at 12:00 PM",
        "client": "Sam",
    }
    assert fake_square.bookings[0].start_at == datetime(2026, 11, 19, 20, 0, tzinfo=UTC)
    assert fake_square.find_customer_by_phone("4085550123").given_name == "Sam"
    times = client.get("/availability", params={"service_id": "SV_CLIPPER", "date": "2026-11-19"})
    assert times.json()["slots"][0]["start"] == "2026-11-19T13:00"


def test_a_taken_time_returns_409(client):
    client.post("/bookings", json=BOOKING)
    response = client.post("/bookings", json=BOOKING | {"phone": "4085550199", "first_name": "Jo"})
    assert response.status_code == 409
    assert "just taken" in response.json()["detail"]


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"phone": "555"}, 422),
        ({"first_name": ""}, 422),
        ({"start": "tomorrow at noon"}, 422),
        ({"start": "2026-11-20T12:00"}, 409),  # closed day
        ({"service_id": "SV_PERM"}, 404),
    ],
)
def test_bad_bookings_are_rejected(client, fake_square, change, status):
    assert client.post("/bookings", json=BOOKING | change).status_code == status
    assert fake_square.bookings == []


def test_square_failure_returns_502(clock):
    class DownSquare:
        def list_services(self):
            raise SquareError("timeout")

    client = TestClient(create_app(backend=DownSquare(), clock=clock))
    response = client.get("/services")
    assert response.status_code == 502
    assert "unavailable" in response.json()["detail"]


def test_calendar_and_chat_share_one_backend(fake_square, clock, monkeypatch):
    seen = {}

    def fake_store(settings, backend):
        seen["backend"] = backend
        return ConversationStore(lambda phone: None)

    monkeypatch.setattr("agent_service.app.build_conversation_store", fake_store)
    TestClient(create_app(backend=fake_square, clock=clock)).post("/chat", json={"message": "hi"})

    assert seen["backend"] is fake_square
