"""HTTP entry point for the agent service."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from agent_service import __version__
from agent_service.booking import Clock, utc_now
from agent_service.booking_api import router as booking_router
from agent_service.conversations import ConversationStore, build_conversation_store
from agent_service.settings import get_settings
from agent_service.square.backend import BookingBackend
from agent_service.square.client import normalize_phone
from agent_service.wiring import build_backend

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


def create_app(
    store: ConversationStore | None = None,
    backend: BookingBackend | None = None,
    clock: Clock = utc_now,
) -> FastAPI:
    """Build the app. Anything not passed in is built from settings on first use.

    The chat agents and the booking API share one Square backend, so bookings made in
    either place are visible to both (this matters for the in-memory practice shop).
    """
    app = FastAPI(title="agentic-barbershop agent service", version=__version__)
    app.state.store = store
    app.state.backend = backend
    app.state.clock = clock

    def get_backend() -> BookingBackend:
        if app.state.backend is None:
            app.state.backend = build_backend(get_settings())
        return app.state.backend

    app.state.get_backend = get_backend

    def get_store(request: Request) -> ConversationStore:
        if request.app.state.store is None:
            request.app.state.store = build_conversation_store(get_settings(), get_backend())
        return request.app.state.store

    app.include_router(booking_router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """The API has no page of its own; send people to its interactive docs."""
        return RedirectResponse("/docs")

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
