from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

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
