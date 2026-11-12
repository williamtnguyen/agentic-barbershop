# Working in this repo

## Ground rules
- Square is the system of record for bookings, customers and payments. Never store a second copy of a booking as truth; read it from Square.
- All slot times are shown and parsed in `BUSINESS_TIMEZONE` and sent to Square as UTC (RFC 3339). Test any time handling with a fixed timezone.
- Secrets come from environment variables (locally `.env`, deployed from Secrets Manager). Never hardcode keys.
- Twilio webhooks must return within 15 seconds: acknowledge, queue, reply via the API.
- Keep the repo anonymous: never name the business, its site or the barber in code, docs or tests. Business details come from config at runtime.

## Workflow
- Small PRs: one capability each, with tests. Keep the README roadmap checklist and the
  architecture diagram's `planned` class in sync with what a PR ships.
- Before pushing: `uv run ruff check . && uv run ruff format --check . && uv run pytest`.
- No AI attribution in commits or PRs: no `Co-Authored-By` trailers, session links or "Generated with" footers.
- One focused commit per PR where possible; squash fixups before pushing.

## Layout
- `services/agent/`: Python 3.13, FastAPI, Strands agents. Package `agent_service` under `src/`.
- `apps/web/`: Next.js (planned).
- `infra/`: AWS CDK in TypeScript (planned).
