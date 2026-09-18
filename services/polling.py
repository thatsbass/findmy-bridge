"""Application service for one polling cycle."""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import TYPE_CHECKING

from domain.exceptions import ReportFetchError, RepositoryError
from domain.ports import TagRepository
from services.publishing import PublishingService

if TYPE_CHECKING:
    from integrations.apple.fetcher import AppleFetcher

logger = logging.getLogger(__name__)

_cycle_id: contextvars.ContextVar[str] = contextvars.ContextVar("cycle_id", default="-")


def get_cycle_id() -> str:
    return _cycle_id.get()


class PollingService:
    """Execute one application-level polling cycle."""

    def __init__(
        self,
        repository: TagRepository,
        report_fetcher: AppleFetcher,
        publishing_service: PublishingService,
    ) -> None:
        self._repository = repository
        self._report_fetcher = report_fetcher
        self._publishing_service = publishing_service

    async def run_cycle(self) -> None:
        token = _cycle_id.set(uuid.uuid4().hex[:8])
        try:
            await self._run_cycle()
        finally:
            _cycle_id.reset(token)

    async def _run_cycle(self) -> None:
        try:
            tags = await self._repository.load_active_tags()
        except RepositoryError:
            logger.exception("Failed to load active tags")
            return

        if not tags:
            logger.info("No active tags to poll")
            return

        logger.info("Cycle started — %d active tags", len(tags))

        try:
            positions_by_tag = await self._report_fetcher.fetch_all(tags)
        except ReportFetchError:
            logger.exception("Batch fetch failed")
            return

        published = await self._publishing_service.publish_latest_by_tag(positions_by_tag)
        logger.info(
            "Cycle complete — %d new position(s) published",
            published,
        )
