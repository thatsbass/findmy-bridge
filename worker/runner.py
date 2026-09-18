"""Application composition and worker lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import logging
import signal
from pathlib import Path

from config.settings import Config
from worker.scheduler import PollingWorker

logger = logging.getLogger("findmy_service")


async def run_worker(config: Config) -> None:
    """Build dependencies, run the worker, and shut down cleanly."""
    from infrastructure.database.tags import PostgresTagRepository
    from integrations.anisette.provider import create_provider
    from integrations.apple.fetcher import AppleFetcher
    from integrations.apple.session import AppleSession
    from integrations.backend.publisher import HttpPositionPublisher
    from integrations.notifications.provider import NotificationDispatcher, NotificationProvider
    from integrations.notifications.slack import SlackAlerter
    from services.polling import PollingService
    from services.publishing import PublishingService
    from api.app import create_app
    import uvicorn

    async with AsyncExitStack() as resources:
        session = AppleSession(
            apple_id=config.apple_id,
            apple_password=config.apple_password,
            session_file=Path(config.apple_session_path),
            libs_path=Path(config.anisette_libs_path),
            provider_factory=lambda libs_path: create_provider(
                config.anisette_provider,
                libs_path=libs_path,
                url=config.anisette_url,
            ),
        )
        await session.connect()
        resources.push_async_callback(session.close)

        store = PostgresTagRepository(config.database_url)
        await store.connect()
        resources.push_async_callback(store.close)

        publisher = HttpPositionPublisher(config.backend_url, config.backend_api_key)
        resources.push_async_callback(publisher.close)

        providers: list[NotificationProvider] = []
        if config.slack_webhook_url:
            providers.append(SlackAlerter(config.slack_webhook_url))
        else:
            logger.warning("SLACK_WEBHOOK_URL not set — Slack alerts disabled")

        notification_dispatcher = NotificationDispatcher(providers)
        resources.push_async_callback(notification_dispatcher.close)

        fetcher = AppleFetcher(session, alerter=notification_dispatcher)
        polling_service = PollingService(
            repository=store,
            report_fetcher=fetcher,
            publishing_service=PublishingService(publisher),
        )
        worker = PollingWorker(polling_service, config.poll_interval_seconds)
        api_config = uvicorn.Config(
            create_app(),
            host="0.0.0.0",
            port=config.health_port,
            log_config=None,
        )
        api_server = uvicorn.Server(api_config)
        api_task = asyncio.create_task(api_server.serve())

        async def stop_api() -> None:
            api_server.should_exit = True
            await api_task

        resources.push_async_callback(stop_api)

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def request_shutdown() -> None:
            logger.info("Shutdown signal received")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, request_shutdown)

        worker_task = asyncio.create_task(worker.run())
        try:
            await stop_event.wait()
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
            logger.info("Find My polling service stopped")
