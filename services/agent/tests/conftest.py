import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from strands.models import Model

from agent_service.square.fake import FakeSquareGateway

LA = ZoneInfo("America/Los_Angeles")
# Wednesday Nov 18, 2026, noon local. The fake shop opens Thursday 12-7 and Saturday 10-4.
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=LA)


@pytest.fixture
def clock():
    return lambda: NOW


@pytest.fixture
def fake_square(clock):
    return FakeSquareGateway(LA, clock=clock)


class ScriptedModel(Model):
    """A stand-in model that replays scripted steps through the real Strands loop.

    Each step is {"tool": name, "input": {...}} or {"text": "..."}. Every request the
    agent makes is recorded in `requests` (the last message the model was shown).
    """

    def __init__(self, steps):
        self.steps = list(steps)
        self.requests = []

    def update_config(self, **kwargs):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.requests.append(messages[-1])
        step = self.steps.pop(0)
        yield {"messageStart": {"role": "assistant"}}
        if "tool" in step:
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {"toolUseId": f"t{len(self.requests)}", "name": step["tool"]}
                    }
                }
            }
            yield {
                "contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step["input"])}}}
            }
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": step["text"]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}

    def last_tool_result(self):
        content = self.requests[-1]["content"][0]["toolResult"]["content"][0]
        return content.get("json") or json.loads(content["text"])


@pytest.fixture
def scripted_model():
    """Factory: scripted_model(steps) -> ScriptedModel."""
    return ScriptedModel
