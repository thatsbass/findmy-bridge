"""Backend integration for publishing positions."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from domain.exceptions import PositionPublishError
from domain.positions.model import Position

logger = logging.getLogger(__name__)

_PUSH_PATH = "/api/internal/positions"
_MAX_ATTEMPTS = 3
_REQUEST_TIMEOUT = 15.0


class BackendResponse(Protocol):
    status_code: int


class BackendTransport(Protocol):
    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> BackendResponse: ...

    async def close(self) -> None: ...


class BackendTransportError(Exception):
    """A temporary failure while communicating with the backend."""


class BackendPublishError(PositionPublishError):
    """The backend rejected or did not accept a position."""

    def __init__(self, tag_id: str, attempts: int, status_code: int | None = None) -> None:
        detail = f"HTTP {status_code}" if status_code is not None else "transport failure"
        super().__init__(
            f"Failed to publish position for tag {tag_id} after {attempts} attempts ({detail})"
        )
        self.tag_id = tag_id
        self.attempts = attempts
        self.status_code = status_code


class _HttpxTransport:
    """Adapter keeping the HTTP client library out of publisher logic."""

    def __init__(self) -> None:
        import httpx

        self._httpx = httpx
        self._client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> BackendResponse:
        try:
            return await self._client.post(url, json=json, headers=headers)
        except self._httpx.RequestError as exc:
            raise BackendTransportError from exc

    async def close(self) -> None:
        await self._client.aclose()


class HttpPositionPublisher:
    """Publish positions with bounded, status-aware retries."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        transport: BackendTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        self._transport = transport or _HttpxTransport()
        self._sleep = sleep

    async def close(self) -> None:
        await self._transport.close()

    async def publish(self, position: Position) -> None:
        payload = self._serialize(position)
        last_status: int | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._transport.post(
                    f"{self._base_url}{_PUSH_PATH}",
                    json=payload,
                    headers=self._headers,
                )
            except BackendTransportError:
                if attempt == _MAX_ATTEMPTS:
                    raise BackendPublishError(position.tag_id, attempt) from None
                logger.warning(
                    "Backend transport failure while publishing tag=%s; retry %d/%d",
                    position.tag_id,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                )
                await self._sleep(self._backoff(attempt))
                continue

            last_status = response.status_code
            if 200 <= last_status < 300:
                logger.info(
                    "Position published: tag=%s seen_at=%s",
                    position.tag_id,
                    position.timestamp.isoformat(timespec="seconds"),
                )
                return

            if not self._is_retryable_status(last_status) or attempt == _MAX_ATTEMPTS:
                break

            logger.warning(
                "Backend returned HTTP %d while publishing tag=%s; retry %d/%d",
                last_status,
                position.tag_id,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            await self._sleep(self._backoff(attempt))

        raise BackendPublishError(position.tag_id, _MAX_ATTEMPTS, last_status)

    @staticmethod
    def _serialize(position: Position) -> dict[str, object]:
        return {
            "tag_id": position.tag_id,
            "lat": position.lat,
            "lng": position.lng,
            "accuracy": position.accuracy,
            "confidence": position.confidence,
            "timestamp": position.timestamp.isoformat(),
        }

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(attempt * attempt)
