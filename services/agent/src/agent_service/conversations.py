"""Conversations: one agent per conversation, so each client keeps their own context.

Held in process memory for now (lost on restart, capped by count). A persistent store
(Strands session manager on DynamoDB) replaces this when the service is deployed.
"""

import asyncio
import uuid
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, Protocol

from agent_service.agents.front_desk import create_front_desk_agent
from agent_service.settings import Settings
from agent_service.wiring import build_backend, build_model


class ChatAgent(Protocol):
    async def invoke_async(self, prompt: str) -> Any: ...


AgentFactory = Callable[[str | None], ChatAgent]


class ConversationStore:
    def __init__(self, agent_factory: AgentFactory, max_conversations: int = 500):
        self._factory = agent_factory
        self._max = max_conversations
        self._conversations: OrderedDict[str, tuple[ChatAgent, asyncio.Lock]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._conversations)

    def _get_or_create(
        self, conversation_id: str, phone: str | None
    ) -> tuple[ChatAgent, asyncio.Lock]:
        if conversation_id in self._conversations:
            self._conversations.move_to_end(conversation_id)
            return self._conversations[conversation_id]
        entry = (self._factory(phone), asyncio.Lock())
        self._conversations[conversation_id] = entry
        while len(self._conversations) > self._max:
            self._conversations.popitem(last=False)  # drop the least recently used
        return entry

    async def send(
        self, message: str, conversation_id: str | None = None, phone: str | None = None
    ) -> tuple[str, str]:
        """Send a message; returns (conversation_id, reply).

        The phone number is bound when a conversation starts. Messages within one
        conversation are handled one at a time, in order.
        """
        conversation_id = conversation_id or uuid.uuid4().hex
        agent, lock = self._get_or_create(conversation_id, phone)
        async with lock:
            result = await agent.invoke_async(message)
        return conversation_id, str(result).strip()


def build_conversation_store(settings: Settings) -> ConversationStore:
    backend = build_backend(settings)
    model = build_model(settings)

    def factory(phone: str | None) -> ChatAgent:
        return create_front_desk_agent(backend, settings, model, client_phone=phone)

    return ConversationStore(factory)
