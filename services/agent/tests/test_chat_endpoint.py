import asyncio

import pytest
from fastapi.testclient import TestClient

from agent_service.app import create_app
from agent_service.conversations import ConversationStore


class EchoAgent:
    """Stands in for a model-backed agent: remembers what it was told."""

    def __init__(self, phone):
        self.phone = phone
        self.messages = []

    async def invoke_async(self, prompt):
        self.messages.append(prompt)
        await asyncio.sleep(0)
        return f"  heard {len(self.messages)}: {prompt}  "


class FailingAgent(EchoAgent):
    async def invoke_async(self, prompt):
        raise RuntimeError("model is down")


@pytest.fixture
def agents():
    return []


@pytest.fixture
def client(agents):
    def factory(phone):
        agent = EchoAgent(phone)
        agents.append(agent)
        return agent

    return TestClient(create_app(ConversationStore(factory)))


def test_new_conversation_gets_an_id_and_reply(client):
    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"]
    assert body["reply"] == "heard 1: hi"


def test_follow_ups_reuse_the_same_agent(client, agents):
    first = client.post("/chat", json={"message": "need a cut"}).json()
    second = client.post(
        "/chat", json={"message": "saturday?", "conversation_id": first["conversation_id"]}
    ).json()

    assert second["conversation_id"] == first["conversation_id"]
    assert second["reply"] == "heard 2: saturday?"
    assert len(agents) == 1


def test_separate_conversations_get_separate_agents(client, agents):
    client.post("/chat", json={"message": "a", "conversation_id": "one"})
    client.post("/chat", json={"message": "b", "conversation_id": "two"})
    assert [a.messages for a in agents] == [["a"], ["b"]]


def test_phone_is_normalized_and_bound_at_start(client, agents):
    client.post("/chat", json={"message": "hi", "conversation_id": "c", "phone": "(408) 555-0123"})
    client.post("/chat", json={"message": "again", "conversation_id": "c", "phone": "4085550199"})
    assert len(agents) == 1
    assert agents[0].phone == "+14085550123"


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 2001},
        {"message": "hi", "phone": "555"},
        {"message": "hi", "conversation_id": ""},
    ],
)
def test_bad_requests_are_rejected(client, payload):
    assert client.post("/chat", json=payload).status_code == 422


def test_agent_failure_returns_502():
    client = TestClient(create_app(ConversationStore(FailingAgent)))
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 502
    assert "couldn't respond" in response.json()["detail"]


def test_oldest_conversations_are_dropped_past_the_cap():
    store = ConversationStore(EchoAgent, max_conversations=2)
    for cid in ["a", "b", "a", "c"]:  # "a" is touched again, so "b" is the oldest
        asyncio.run(store.send("hi", conversation_id=cid))
    assert len(store) == 2
    assert set(store._conversations) == {"a", "c"}


def test_messages_in_one_conversation_are_handled_in_order():
    store = ConversationStore(EchoAgent)

    async def burst():
        return await asyncio.gather(*(store.send(m, conversation_id="c") for m in "abc"))

    replies = [reply for _, reply in asyncio.run(burst())]
    assert replies == ["heard 1: a", "heard 2: b", "heard 3: c"]


def test_health_needs_no_model_or_square_config():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
