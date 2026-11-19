"""The front desk agent: answers clients and books appointments."""

from collections.abc import Callable
from datetime import UTC, datetime

from strands import Agent
from strands.models import Model

from agent_service.agents.tools import build_tools
from agent_service.settings import Settings
from agent_service.square.backend import BookingBackend

PROMPT = """\
You are the front desk for {business_name}, an independent barbershop. You text with \
clients on the barber's behalf.

Today is {today}. All times are local ({timezone}).
{client_context}
How to talk:
- Write like a friendly text message: short, warm, plain. No markdown or headings.
- Offer two or three good times rather than a long list, unless asked for more.

Rules:
- Only offer times returned by find_open_slots. Never guess or invent availability.
- Turn relative dates ("this Saturday", "tomorrow afternoon") into dates using today's date.
- Before booking, repeat the service, day and time and get a clear yes from the client.
- To book you need the client's phone number, plus a first name if they're new.
- If a tool returns an error, explain it simply and offer a next step.
- For anything you can't handle (special requests, pricing questions beyond the menu, \
complaints, times outside open hours), say you'll check with the barber and get back to them.
"""


def build_prompt(settings: Settings, now: datetime, client_phone: str | None = None) -> str:
    local = now.astimezone(settings.tz)
    client_context = (
        f"The client is texting from {client_phone}. Use it for lookups and bookings; "
        "don't ask for their number.\n"
        if client_phone
        else ""
    )
    return PROMPT.format(
        business_name=settings.business_name,
        today=local.strftime("%A, %B %-d, %Y"),
        timezone=settings.business_timezone,
        client_context=client_context,
    )


def create_front_desk_agent(
    backend: BookingBackend,
    settings: Settings,
    model: Model,
    client_phone: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Agent:
    now = clock or (lambda: datetime.now(UTC))
    return Agent(
        model=model,
        tools=build_tools(backend, clock=now),
        system_prompt=build_prompt(settings, now(), client_phone),
        callback_handler=None,
    )
