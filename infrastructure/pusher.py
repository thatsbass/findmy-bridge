"""HTTP implementation of PositionPublisher."""

from __future__ import annotations

import asyncio
import logging

import httpx

from domain.models import Position

logger = logging.getLogger(__name__)

_PUSH_PATH = "/api/internal/positions"
_MAX_RETRIES = 3
_TIMEOUT = 15.0


class HttpPositionPublisher:
    """Sends position reports to a backend HTTP endpoint with retry."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)

    async def close(self) -> None:
        await self._client.aclose()

    async def publish(self, position: Position) -> None:
        url = f"{self._base_url}{_PUSH_PATH}"
        payload = {
            "tag_id": position.tag_id,
            "lat": position.lat,
            "lng": position.lng,
            "accuracy": position.accuracy,
            "confidence": position.confidence,
            "timestamp": position.timestamp.isoformat(),
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await self._client.post(url, json=payload, headers=self._headers)
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "Position published: tag=%s lat=%.6f lng=%.6f seen_at=%s",
                        position.tag_id,
                        position.lat,
                        position.lng,
                        position.timestamp.isoformat(timespec="seconds"),
                    )
                    return
                logger.warning("Publish attempt %d/%d: HTTP %d", attempt, _MAX_RETRIES, resp.status_code)
            except httpx.RequestError as e:
                logger.warning("Publish attempt %d/%d: %s", attempt, _MAX_RETRIES, e)

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(attempt * attempt)

        raise RuntimeError(f"Failed to publish position for {position.tag_id} after {_MAX_RETRIES} attempts")
