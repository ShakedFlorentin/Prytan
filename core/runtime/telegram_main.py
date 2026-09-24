"""Telegram bot entrypoint — wires TelegramAdapter → Orchestrator.

Environment variables required:
    TELEGRAM_BOT_TOKEN   your bot token from @BotFather
    TELEGRAM_CHAT_ID     the numeric chat/user ID that the bot listens to

Run from the project root:
    python -m core.runtime.telegram_main

Deploy note: always launch from the project root, not a transient cwd.
A deleted cwd kills the long-running process.
"""
from __future__ import annotations
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

_RETRY_SLEEP = 5   # seconds to wait after a transient error before retrying


def run_loop(config, *, cwd: str, adapter, orchestrator=None,
             sleep_fn=time.sleep) -> None:
    """Polling loop: read from Telegram, handle via Orchestrator, reply."""
    from core.runtime.orchestrator import Orchestrator
    from core.runtime.metering import BudgetExceededError

    orch = orchestrator or Orchestrator(config, cwd=cwd)
    log.info("Telegram bot started (chat_id=%s)", adapter.chat_id)

    while True:
        try:
            msg = adapter.read()
            if msg is not None:
                log.info("← %r", msg[:120])
                try:
                    reply = orch.handle(msg)
                except BudgetExceededError as exc:
                    reply = f"⚠️ Budget cap reached: {exc}. Contact the org owner."
                adapter.write(reply)
                log.info("→ %r", reply[:120])
        except KeyboardInterrupt:
            log.info("Shutting down.")
            break
        except Exception as exc:            # transient network / subprocess error
            log.error("Bot loop error: %s", exc, exc_info=True)
            sleep_fn(_RETRY_SLEEP)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cwd = Path.cwd()

    from core.config import Config
    from core.runtime.adapters.telegram import TelegramAdapter

    config = Config.load(cwd / "config.yaml")
    adapter = TelegramAdapter.from_env()
    run_loop(config, cwd=str(cwd), adapter=adapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
