"""Find My polling service entry point.

Wires dependencies, starts the polling worker and health server,
handles graceful shutdown on SIGTERM/SIGINT.

Usage: python main.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from apple.fetcher import AppleFetcher
from apple.session import AppleSession
from application.poll_cycle import PollCycle, PollingWorker
from config import Config
from config.logging_setup import setup_logging
from health.server import HealthServer
from infrastructure.pusher import HttpPositionPublisher
from infrastructure.store import PostgresTagRepository
from notifications.provider import NotificationDispatcher, NotificationProvider
from notifications.slack import SlackAlerter

logger = logging.getLogger("findmy_service")

_SESSION_FILE = Path("account_session.json")
_ANISETTE_LIBS = Path(".anisette_libs")


async def main() -> None:
    cfg = Config.load()
    setup_logging(cfg)

    logger.info("Find My polling service starting (env=%s)", cfg.env)

    session = AppleSession(
        apple_id=cfg.apple_id,
        apple_password=cfg.apple_password,
        session_file=_SESSION_FILE,
        libs_path=_ANISETTE_LIBS,
    )
    await session.connect()

    store = PostgresTagRepository(cfg.database_url)
    await store.connect()

    pusher = HttpPositionPublisher(cfg.backend_url, cfg.backend_api_key)
    notification_providers: list[NotificationProvider] = []
    if cfg.slack_webhook_url:
        notification_providers.append(SlackAlerter(cfg.slack_webhook_url))
    else:
        logger.warning("SLACK_WEBHOOK_URL not set — Slack alerts disabled")
    alerter = NotificationDispatcher(notification_providers)
    fetcher = AppleFetcher(session, alerter=alerter)

    cycle = PollCycle(
        repo=store,
        publisher=pusher,
        fetcher=fetcher,
    )
    worker = PollingWorker(cycle, cfg.poll_interval_seconds)

    health = HealthServer(cfg.health_port)
    await health.start()

    # Shutdown order matters: worker must finish before closing its dependencies.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    worker_task = asyncio.create_task(worker.run())
    await stop_event.wait()

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    await health.stop()
    await pusher.close()
    await session.close()
    await store.close()
    logger.info("Find My polling service stopped")


if __name__ == "__main__":
    asyncio.run(main())
