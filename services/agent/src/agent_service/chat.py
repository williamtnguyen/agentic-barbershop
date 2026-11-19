"""Chat with the front desk agent in your terminal.

    uv run --package agent-service python -m agent_service.chat [--phone 4085550123]

Uses SQUARE_MODE (live or fake) and MODEL_PROVIDER from the environment or .env.
"""

import argparse

from agent_service.agents.front_desk import create_front_desk_agent
from agent_service.settings import get_settings
from agent_service.wiring import build_backend, build_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phone", help="pretend to be texting from this number")
    args = parser.parse_args()

    settings = get_settings()
    backend = build_backend(settings)
    agent = create_front_desk_agent(
        backend, settings, build_model(settings), client_phone=args.phone
    )

    print(
        f"Front desk ({settings.model_provider} model, Square {settings.square_mode}). "
        "Type 'quit' to exit.\n"
    )
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if message.lower() in {"quit", "exit"}:
            return
        if message:
            print(f"desk> {agent(message)}\n")


if __name__ == "__main__":
    main()
