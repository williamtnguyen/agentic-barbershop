"""HTTP entry point for the agent service."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from agent_service import __version__
from agent_service.conversations import ConversationStore, build_conversation_store
from agent_service.settings import get_settings
from agent_service.square.client import normalize_phone

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message is blank")
        return value

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str


def create_app(store: ConversationStore | None = None) -> FastAPI:
    """Build the app. Without a store, one is built from settings on the first chat."""
    app = FastAPI(title="agentic-barbershop agent service", version=__version__)
    app.state.store = store

    def get_store(request: Request) -> ConversationStore:
        if request.app.state.store is None:
            request.app.state.store = build_conversation_store(get_settings())
        return request.app.state.store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/chat")
    async def chat(
        body: ChatRequest, store: Annotated[ConversationStore, Depends(get_store)]
    ) -> ChatResponse:
        try:
            conversation_id, reply = await store.send(
                body.message, conversation_id=body.conversation_id, phone=body.phone
            )
        except Exception as error:
            logger.exception("chat failed")
            raise HTTPException(502, "The assistant couldn't respond. Try again.") from error
        return ChatResponse(conversation_id=conversation_id, reply=reply)

    return app


app = create_app()
