"""The real Strands agent loop with a scripted model: model -> tools -> fake Square -> reply."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from agent_service.agents.front_desk import create_front_desk_agent
from agent_service.app import create_app
from agent_service.conversations import ConversationStore
from agent_service.settings import Settings

PHONE = "+14085550123"
THURSDAY_NOON_UTC = datetime(2026, 11, 19, 20, 0, tzinfo=UTC)


@pytest.fixture
def settings():
    return Settings(_env_file=None, business_name="Test Shop")


def test_two_turn_booking_runs_tools_and_books(fake_square, clock, settings, scripted_model):
    model = scripted_model(
        [
            {
                "tool": "find_open_slots",
                "input": {"service": "clipper", "start_date": "2026-11-19"},
            },
            {"text": "I've got noon Thursday. Want it?"},
            {
                "tool": "book_appointment",
                "input": {
                    "service": "Clipper Cut",
                    "start": "2026-11-19T12:00",
                    "phone": PHONE,
                    "first_name": "Sam",
                },
            },
            {"text": "You're booked for Thursday at noon."},
        ]
    )
    agent = create_front_desk_agent(fake_square, settings, model, client_phone=PHONE, clock=clock)

    first = str(agent("clipper cut thursday?")).strip()
    slots = model.last_tool_result()["slots"]
    second = str(agent("yes")).strip()

    assert first == "I've got noon Thursday. Want it?"
    assert slots[0]["start"] == "2026-11-19T12:00"
    assert model.last_tool_result()["booked"] is True
    assert second == "You're booked for Thursday at noon."
    assert [b.start_at for b in fake_square.bookings] == [THURSDAY_NOON_UTC]
    assert fake_square.find_customer_by_phone(PHONE).given_name == "Sam"


def test_tool_errors_are_shown_to_the_model(fake_square, clock, settings, scripted_model):
    model = scripted_model(
        [
            {
                "tool": "book_appointment",
                "input": {
                    "service": "Clipper Cut",
                    "start": "2026-11-20T12:00",  # Friday: closed
                    "phone": PHONE,
                    "first_name": "Sam",
                },
            },
            {"text": "Sorry, we're closed Fridays."},
        ]
    )
    agent = create_front_desk_agent(fake_square, settings, model, client_phone=PHONE, clock=clock)

    agent("friday at noon")

    assert "isn't open" in model.last_tool_result()["error"]
    assert fake_square.bookings == []


def test_chat_endpoint_drives_a_real_agent(fake_square, clock, settings, scripted_model):
    model = scripted_model(
        [
            {"tool": "list_services", "input": {}},
            {"text": "Full Service $40, Clipper Cut $30, Beard Trim $10."},
        ]
    )

    def factory(phone):
        return create_front_desk_agent(
            fake_square, settings, model, client_phone=phone, clock=clock
        )

    client = TestClient(create_app(ConversationStore(factory)))
    response = client.post("/chat", json={"message": "prices?", "phone": "4085550123"})

    assert response.status_code == 200
    assert response.json()["reply"] == "Full Service $40, Clipper Cut $30, Beard Trim $10."
    assert [s["name"] for s in model.last_tool_result()] == [
        "Full Service",
        "Clipper Cut",
        "Beard Trim",
    ]
