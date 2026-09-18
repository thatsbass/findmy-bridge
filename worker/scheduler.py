"""Scheduling concerns for the polling worker."""

from __future__ import annotations

import asyncio
import logging

from services.polling import PollingService

logger = logging.getLogger(__name__)


class PollingWorker:
    """Run one polling cycle immediately and then at a fixed interval."""

    def __init__(self, service: PollingService, interval_seconds: int) -> None:
        self._service = service
        self._interval = interval_seconds

    async def run(self) -> None:
        """Block until cancelled while scheduling polling cycles."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self._service.run_cycle,
            "interval",
            seconds=self._interval,
            id="poll_cycle",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started — polling every %ds", self._interval)

        await self._service.run_cycle()

        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("PollingWorker shutting down")
        finally:
            scheduler.shutdown(wait=False)
