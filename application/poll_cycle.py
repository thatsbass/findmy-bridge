"""Polling orchestration — one full cycle and the APScheduler wrapper."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apple.fetcher import AppleFetcher
from domain.models import Position
from domain.ports import PositionPublisher, TagRepository

logger = logging.getLogger(__name__)

_cycle_id: contextvars.ContextVar[str] = contextvars.ContextVar("cycle_id", default="-")


def get_cycle_id() -> str:
    return _cycle_id.get()


class PollCycle:
    """
    EXECUTES ONE POLLING CYCLE:
    1. load tags
    2. batch fetch
    3. publish latest.

    Apple returns a rolling 7-day window of every report each cycle. We publish
    only the freshest report per tag, and only if it is newer than the last one
    we already published (high-water mark). This stops re-publishing stale
    history every cycle — including when a tag stops being seen entirely.

    The high-water mark is in-memory: on restart we may re-publish the latest
    position once per tag (harmless if the backend dedups by timestamp).
    """

    def __init__(
        self,
        repo: TagRepository,
        publisher: PositionPublisher,
        fetcher: AppleFetcher,
    ) -> None:
        self._repo = repo
        self._publisher = publisher
        self._fetcher = fetcher
        self._last_seen: dict[str, datetime] = {}

    async def run(self) -> None:
        token = _cycle_id.set(uuid.uuid4().hex[:8])
        try:
            await self._run()
        finally:
            _cycle_id.reset(token)

    async def _run(self) -> None:
        try:
            tags = await self._repo.load_active_tags()
        except Exception:
            logger.exception("Failed to load active tags")
            return

        if not tags:
            logger.info("No active tags to poll")
            return

        logger.info("Cycle started — %d active tags", len(tags))

        try:
            positions_by_tag = await self._fetcher.fetch_all(tags)
        except Exception:
            logger.exception("Batch fetch failed")
            return

        publish_tasks = [
            asyncio.create_task(self._publish_latest(tag_id, positions))
            for tag_id, positions in positions_by_tag.items()
            if positions
        ]
        published = await asyncio.gather(*publish_tasks, return_exceptions=True)
        logger.info("Cycle complete — %d new position(s) published", sum(r is True for r in published))

    async def _publish_latest(self, tag_id: str, positions: list[Position]) -> bool:
        """Publish only the freshest report, and only if newer than the last one seen."""
        latest = max(positions, key=lambda p: p.timestamp)

        last = self._last_seen.get(tag_id)
        if last is not None and latest.timestamp <= last:
            return False

        try:
            await self._publisher.publish(latest)
        except Exception:
            logger.exception("Failed to publish position for tag %s", tag_id)
            return False

        self._last_seen[tag_id] = latest.timestamp
        return True


class PollingWorker:
    """Wraps PollCycle with APScheduler. Runs one cycle immediately then on interval."""

    def __init__(self, cycle: PollCycle, interval_seconds: int) -> None:
        self._cycle = cycle
        self._interval = interval_seconds

    async def run(self) -> None:
        """Block until cancelled. Runs the cycle immediately then on schedule."""
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self._cycle.run,
            "interval",
            seconds=self._interval,
            id="poll_cycle",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started — polling every %ds", self._interval)

        await self._cycle.run()

        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("PollingWorker shutting down")
        finally:
            scheduler.shutdown(wait=False)
