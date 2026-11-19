"""Scripted conversations with a real model. The bar for "ready to deploy".

Skipped by default. Run with model access configured (.env or environment):

    uv run pytest -m scenario -v

Each scenario uses the fake shop on a fixed clock (Wednesday Nov 18, 2026, noon; open
Thursday 12-7 and Saturday 10-4) and checks outcomes, not wording: what got booked,
which tools were called with what, and a few must-mention words.
"""

from datetime import UTC, datetime, timedelta

import pytest

from agent_service.agents.front_desk import create_front_desk_agent
from agent_service.settings import Settings, get_settings
from agent_service.wiring import build_model

pytestmark = pytest.mark.scenario

SAM = "+14085550123"  # returning client
NEW_CLIENT = "+14085550199"
THURSDAY_NOON = datetime(2026, 11, 19, 20, 0, tzinfo=UTC)
SATURDAY_10AM = datetime(2026, 11, 21, 18, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def model():
    settings = get_settings()
    try:
        built = build_model(settings)
    except ValueError as error:
        pytest.skip(str(error))
    if settings.model_provider == "bedrock":
        import boto3

        if boto3.Session().get_credentials() is None:
            pytest.skip("no AWS credentials for Bedrock")
    return built


class Chat:
    def __init__(self, agent):
        self.agent = agent
        self.transcript: list[str] = []

    def say(self, text: str) -> str:
        reply = str(self.agent(text)).strip()
        self.transcript += [f"client: {text}", f"desk:   {reply}"]
        return reply

    def tool_calls(self, name: str) -> list[dict]:
        calls = []
        for message in self.agent.messages:
            for block in message["content"]:
                use = block.get("toolUse")
                if use and use["name"] == name:
                    calls.append(use["input"])
        return calls

    def __str__(self) -> str:
        return "\n".join(self.transcript)


@pytest.fixture
def chat(fake_square, clock, model):
    fake_square.create_customer(SAM, "Sam")
    settings = Settings(_env_file=None, business_name="Test Shop")

    def start(phone: str | None = SAM) -> Chat:
        agent = create_front_desk_agent(
            fake_square, settings, model, client_phone=phone, clock=clock
        )
        return Chat(agent)

    return start


def booked_times(fake_square):
    return [b.start_at for b in fake_square.bookings]


def test_answers_menu_questions_without_booking(chat, fake_square):
    c = chat()
    reply = c.say("What do you offer and how much?")
    for price in ("40", "30", "10"):
        assert price in reply, c
    assert fake_square.bookings == [], c


def test_confirms_before_booking_then_books(chat, fake_square):
    c = chat()
    c.say("Can I get a clipper cut this Thursday at noon?")
    assert fake_square.bookings == [], f"booked without confirmation\n{c}"
    c.say("Yes please")
    assert booked_times(fake_square) == [THURSDAY_NOON], c
    assert fake_square.bookings[0].service_variation_id == "SV_CLIPPER", c


def test_new_client_gives_name_and_gets_booked(chat, fake_square):
    c = chat(NEW_CLIENT)
    c.say("Hi! Can you book me a beard trim Saturday at 10am?")
    c.say("I'm Jordan. Yes, book it.")
    if not fake_square.bookings:
        c.say("Yes")
    assert booked_times(fake_square) == [SATURDAY_10AM], c
    assert fake_square.find_customer_by_phone(NEW_CLIENT).given_name == "Jordan", c


def test_resolves_relative_dates(chat, fake_square):
    c = chat()
    c.say("What times do you have this Saturday for a full service?")
    searches = c.tool_calls("find_open_slots")
    assert any(s.get("start_date") == "2026-11-21" for s in searches), c
    assert fake_square.bookings == [], c


def test_closed_day_offers_open_days(chat, fake_square):
    c = chat()
    reply = c.say("Do you have anything Friday at 3pm for a clipper cut?").lower()
    assert fake_square.bookings == [], c
    assert "thu" in reply or "sat" in reply, c


def test_does_not_book_after_hours(chat, fake_square):
    c = chat()
    c.say("Can I come in Thursday at 8pm for a clipper cut?")
    c.say("Yes, 8pm works for me")
    assert fake_square.bookings == [], c


def test_fully_booked_day_points_elsewhere(chat, fake_square):
    beard = next(s for s in fake_square.list_services() if s.name == "Beard Trim")
    thursday = datetime(2026, 11, 19, 20, 0, tzinfo=UTC)
    for slot in fake_square.find_availability(beard, thursday, thursday + timedelta(hours=8)):
        fake_square.create_booking(slot, "CU_OTHER")
    already = len(fake_square.bookings)

    c = chat()
    reply = c.say("Any beard trim openings Thursday?").lower()
    assert len(fake_square.bookings) == already, c
    assert "sat" in reply, c


def test_hands_off_requests_outside_the_menu(chat, fake_square):
    c = chat()
    reply = c.say("Can you do a perm and a color this week?").lower()
    assert fake_square.bookings == [], c
    assert "barber" in reply or "check" in reply, c


def test_web_client_is_asked_for_a_phone_number(chat, fake_square):
    c = chat(phone=None)
    c.say("Book me a clipper cut Thursday at noon")
    reply = c.say("Yes").lower()
    assert fake_square.bookings == [], c
    assert "number" in reply or "phone" in reply, c


def test_repeated_yes_books_once(chat, fake_square):
    c = chat()
    c.say("Clipper cut Thursday at noon please")
    c.say("Yes")
    c.say("Yes, confirmed")
    assert booked_times(fake_square) == [THURSDAY_NOON], c
