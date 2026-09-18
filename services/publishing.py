"""Application service for publishing the latest tag positions."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from domain.exceptions import InvalidPositionError, PositionPublishError
from domain.positions import Position, is_newer_than, latest_position
from domain.ports import PositionPublisher

logger = logging.getLogger(__name__)


class PublishingService:
    """Select and publish new positions using a per-tag high-water mark."""

    def __init__(self, position_publisher: PositionPublisher) -> None:
        self._position_publisher = position_publisher
        self._last_seen: dict[str, datetime] = {}

    async def publish_latest_by_tag(
        self,
        positions_by_tag: dict[str, list[Position]],
    ) -> int:
        tasks = [
            self._publish_latest(tag_id, positions)
            for tag_id, positions in positions_by_tag.items()
            if positions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        published = 0
        for result in results:
            if result is True:
                published += 1
            elif isinstance(result, Exception):
                logger.error(
                    "Unexpected position publishing failure: %s",
                    type(result).__name__,
                    exc_info=(type(result), result, result.__traceback__),
                )
        return published

    async def _publish_latest(self, tag_id: str, positions: list[Position]) -> bool:
        try:
            latest = latest_position(positions)
        except InvalidPositionError:
            logger.exception("Invalid positions received for tag %s", tag_id)
            return False

        last_seen = self._last_seen.get(tag_id)
        if not is_newer_than(latest, last_seen):
            return False

        try:
            await self._position_publisher.publish(latest)
        except PositionPublishError:
            logger.exception("Failed to publish position for tag %s", tag_id)
            return False

        self._last_seen[tag_id] = latest.timestamp
        return True
