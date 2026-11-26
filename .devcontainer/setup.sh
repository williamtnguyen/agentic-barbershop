#!/usr/bin/env bash
# Runs once when the codespace (or dev container) is created.
set -euo pipefail
pipx install uv || pip install --user uv
uv sync --all-packages
(cd apps/web && npm ci)
[ -f .env ] || cp .env.example .env
echo "Ready. Run scripts/dev.sh to start the API and the web app."
