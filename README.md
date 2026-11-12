# agentic-barbershop

An AI front desk and style consultant for an independent barbershop.

Clients text a number (or use the site) to book, reschedule, pay and get a haircut
consultation. The agents talk like a person, loop the barber in when something is
unusual, and keep Square as the single source of truth for bookings and payments.

## Architecture

```mermaid
flowchart LR
  clients["Clients<br/>text, web chat, consult page"]:::people
  barber["Barber<br/>approves by text"]:::people

  api["Agent service<br/>FastAPI"]:::service
  frontdesk["Front desk agent<br/>book, pay, notify"]:::agent
  consult["Consultation agent<br/>photo, face shape, playbook"]:::agent
  memory[("Client memory")]:::data

  square[("Square<br/>bookings, payments")]:::data

  clients --> api
  barber <--> api
  api --> frontdesk
  frontdesk <-->|style questions| consult
  frontdesk --> memory
  consult --> memory
  frontdesk <--> square
  square -.->|webhooks| api

  classDef people fill:#EEEDFE,stroke:#534AB7,color:#26215C
  classDef service fill:#E6F1FB,stroke:#185FA5,color:#042C53
  classDef agent fill:#E1F5EE,stroke:#0F6E56,color:#04342C
  classDef data fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
  classDef planned stroke-dasharray:6 4
  class clients,barber,frontdesk,consult,memory planned
```

Purple: people. Blue: our service. Green: agents. Orange: data and Square.
Dashed borders are planned; solid are built. As pieces ship, remove them from the
`class ... planned` line.

How a text flows: Twilio calls the webhook, the service acknowledges right away and
queues the message, the front desk agent works it (calling the consultation agent or
Square as needed), then replies through the Twilio API. Twilio gives a webhook only
15 seconds, so replies are never sent inline.

## Repo layout

| Path | What | Status |
|---|---|---|
| `services/agent/` | Python service: FastAPI app, Strands agents, Square/Twilio integrations | skeleton |
| `apps/web/` | Next.js site, consult page, compliance pages | planned |
| `infra/` | AWS CDK (TypeScript) | planned |

## Stack

- **Python 3.13** for the agent service: agents ([Strands](https://strandsagents.com)), Square SDK, MediaPipe.
- **TypeScript** for the web app (Next.js), in-browser MediaPipe and AWS CDK.
- **FastAPI** in front of the agents: async (agents mostly wait on Bedrock and Square), Pydantic models, streaming responses for web chat.
- **uv** for Python packaging, **ruff** for lint/format, **pytest** for tests.

## Roadmap

Each line is roughly one small PR.

**Phase 0: foundations**
- [x] Repo skeleton, CI, health endpoint
- [x] Square client: services, availability, booking (timezone-correct), customers by phone
- [ ] Front desk agent v0 with Square tools, local chat CLI
- [ ] Infra: Lambda + API Gateway + DynamoDB + Secrets Manager (CDK)
- [ ] Square webhook endpoint with signature verification

**Phase 0.5: compliance**
- [ ] Web app skeleton with privacy policy, terms and SMS opt-in pages; submit Twilio A2P registration

**Phase 1: agents**
- [ ] Conversation persistence (Strands session manager)
- [ ] Client profile memory
- [ ] Consultation agent v2 (Claude vision + measurements + barber playbook)
- [ ] Front desk calls consultation agent; recommendation into booking

**Phase 2: SMS**
- [ ] Twilio inbound webhook, queue, outbound replies, message batching
- [ ] Barber approval and takeover
- [ ] Notifications from Square webhooks, rebooking nudges, waitlist

**Phase 3: consult page** live MediaPipe overlay, snapshot to agent, book from result

**Later:** payments ledger and reminders, dashboard, try-on images, full site and portfolio

## Development

```bash
uv sync                      # install workspace + dev tools
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pytest                # tests
uv run --package agent-service uvicorn agent_service.app:app --reload   # run the service
```

Copy `.env.example` to `.env` for local secrets. Never commit `.env`.

Read-only check against your Square account (lists services and the next open slots):

```bash
uv run --package agent-service python -m agent_service.square.smoke
```
