#!/usr/bin/env bash
# Start the agent API (port 8000) and the web app (port 5173) together. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (practice shop, no Square account needed)."
fi

trap 'kill 0' EXIT
uv run --package agent-service uvicorn agent_service.app:app --reload --port 8000 &
(cd apps/web && npm run dev -- --port 5173 --strictPort) &
wait
