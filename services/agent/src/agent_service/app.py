"""HTTP entry point for the agent service."""

from fastapi import FastAPI

from agent_service import __version__

app = FastAPI(title="agentic-barbershop agent service", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
