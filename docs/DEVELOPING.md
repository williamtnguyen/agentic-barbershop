# Developing and testing

Step-by-step for trying the app in GitHub Codespaces, what you can test at each stage, and
where keys go.

## 1. Open a codespace

1. On the repo page: **Code → Codespaces → Create codespace on main**.
2. The first start takes a few minutes. It installs Python, Node, the AWS CLI and every
   dependency, and creates `.env` from `.env.example` (practice shop, no keys).
3. Later, reopen the same codespace from **Code → Codespaces**. It stops after 30 idle
   minutes and keeps your files. Delete it when you're done with it.

## 2. Start the app

In the codespace terminal:

```bash
scripts/dev.sh
```

- The web app opens in a new browser tab (or **Ports** tab → "Web app", port 5173).
- The API runs on port 8000. Its interactive docs are at `/docs` on that port.
- Ports are private to your GitHub account unless you change their visibility.
- Ctrl+C stops both.

## 3. What you can test

| Setup | What works | What doesn't |
|---|---|---|
| **Nothing configured** (default) | **Book** tab end to end against the practice shop (open Thursday 12–7, Saturday 10–4; bookings reset when the server restarts). All automated tests: `uv run pytest` and `cd apps/web && npm test`. API docs at `:8000/docs`. | **Chat** tab loads, but every message shows "The front desk didn't answer", because there's no AI model. |
| **+ model access** (section 5) | Chat replies from Claude, booking into the practice shop. Real-model scenario tests: `uv run pytest -m scenario -v`. Terminal chat: `uv run --package agent-service python -m agent_service.chat --phone 4085550123`. | Real services and calendar (still the practice shop). |
| **+ Square sandbox** (section 6) | Both tabs use your Square sandbox: its services, hours and bookings, visible in the sandbox Square Dashboard. Read-only check: `uv run --package agent-service python -m agent_service.square.smoke`. | |
| **Not built yet** | | Texting, deployed site, admin area, door lock, payments, consultation. |

## 4. Where keys go

Never commit keys. The app reads settings from environment variables first, then from
`.env` in the repo root.

| Where | Use it for | Lifetime |
|---|---|---|
| **Codespaces secrets** (recommended) | Anything you'll reuse: Square token, Anthropic key | Encrypted by GitHub; injected as environment variables into every codespace for this repo; override `.env` |
| **`.env`** in the repo root | Quick experiments and switches like `SQUARE_MODE` | Only on that machine or that one codespace; gitignored; gone when the codespace is deleted |

To add a Codespaces secret: <https://github.com/settings/codespaces> → **New secret** →
name and value → **Repository access**: `agentic-barbershop`. A running codespace only
sees new or changed secrets after you stop and restart it.

| Variable | What | Where to get it |
|---|---|---|
| `SQUARE_MODE` | `fake` (practice shop) or `live` (Square) | Your choice |
| `SQUARE_ENVIRONMENT` | `sandbox` or `production` | Your choice; stay on `sandbox` for testing |
| `SQUARE_ACCESS_TOKEN` | Square API token | Square Developer Console → your app → **Credentials** |
| `SQUARE_LOCATION_ID` | Which location to book into | Square Developer Console → your app → **Locations** |
| `MODEL_PROVIDER` | `bedrock` (default) or `anthropic` | Your choice |
| `AWS_PROFILE`, `AWS_REGION` | Which AWS sign-in and region to use for Bedrock | Section 5 |
| `BEDROCK_MODEL_ID` | Optional; empty uses Strands' default Claude model | Bedrock console → **Model catalog** |
| `ANTHROPIC_API_KEY` | Claude without AWS | <https://console.anthropic.com> → API keys |
| `BUSINESS_NAME`, `VITE_BUSINESS_NAME` | Shop name the agent and web app show | Your choice |

In production these move to AWS Secrets Manager; `.env` and Codespaces secrets are for
development only.

## 5. Model access (for Chat)

Pick one.

**Claude on AWS Bedrock** (same account the app will deploy to)

1. Create an AWS account and a user with the `AmazonBedrockFullAccess` policy (IAM
   Identity Center recommended).
2. In the Bedrock console, open **Model catalog**, choose an Anthropic Claude model and
   submit the one-time use-case form if it asks. Access can take up to 15 minutes.
3. In the codespace terminal, sign in. The `--use-device-code` flag lets you approve the
   sign-in in your own browser, which a remote codespace needs:

   ```bash
   aws configure sso --use-device-code      # first time; name the profile, e.g. "dev"
   aws sso login --profile dev --use-device-code   # when the session expires
   ```

4. Set `AWS_PROFILE=dev` (and `AWS_REGION` if not `us-west-2`) in `.env` or as a
   Codespaces secret. The sign-in itself is stored in the codespace (`~/.aws`), so a new
   codespace needs step 3 again.

**Anthropic API key** (no AWS): set `MODEL_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`
as Codespaces secrets.

## 6. Square sandbox (for real Square data)

1. At <https://developer.squareup.com>, open (or create) your app and switch to **Sandbox**.
2. From the sandbox test account, open the **Square Dashboard** and set up Appointments:
   add your services, mark them bookable online, and set your availability.
3. Copy the sandbox **access token** and **location ID** into Codespaces secrets
   `SQUARE_ACCESS_TOKEN` and `SQUARE_LOCATION_ID`, and set `SQUARE_MODE=live`,
   `SQUARE_ENVIRONMENT=sandbox`.
4. Restart the codespace, then run the read-only check:
   `uv run --package agent-service python -m agent_service.square.smoke`. It should list
   your services and the next open times.

Never point a development setup at `production` until the app is deployed and tested:
bookings made there are real.

## 7. Before you push

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
cd apps/web && npm run typecheck && npm test && npm run build
```

CI runs the same checks on every pull request.
