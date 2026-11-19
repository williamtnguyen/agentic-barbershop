import pytest

from agent_service.agents.front_desk import create_front_desk_agent
from agent_service.settings import Settings
from agent_service.wiring import build_backend, build_model


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        business_name="Test Shop",
        square_mode="fake",
        model_provider="anthropic",
        anthropic_api_key="test-key",
    )


def test_agent_has_front_desk_tools_and_dated_prompt(settings, fake_square, clock):
    agent = create_front_desk_agent(fake_square, settings, build_model(settings), clock=clock)

    assert sorted(agent.tool_names) == [
        "book_appointment",
        "find_open_slots",
        "list_services",
        "lookup_client",
    ]
    assert "Test Shop" in agent.system_prompt
    assert "Wednesday, November 18, 2026" in agent.system_prompt
    assert "America/Los_Angeles" in agent.system_prompt
    assert "texting from" not in agent.system_prompt


def test_known_phone_is_given_to_the_agent(settings, fake_square, clock):
    agent = create_front_desk_agent(
        fake_square, settings, build_model(settings), client_phone="+14085550123", clock=clock
    )
    assert "texting from +14085550123" in agent.system_prompt


def test_wiring_picks_fake_square_and_requires_api_key(settings):
    assert type(build_backend(settings)).__name__ == "FakeSquareGateway"
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_model(settings.model_copy(update={"anthropic_api_key": ""}))
