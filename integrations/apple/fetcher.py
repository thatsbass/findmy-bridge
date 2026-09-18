"""Retrieve and decrypt Apple Find My reports."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

import aiohttp
from findmy.errors import UnauthorizedError
from findmy.keys import KeyPair

from domain.exceptions import ReportFetchError
from domain.positions.model import Position
from domain.tags.model import Tag
from integrations.apple.session import AppleSession
from integrations.notifications.provider import NotificationProvider

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_BACKOFF = 2.0
_REQUEST_TIMEOUT = 60.0
APPLE_BATCH_SIZE = 500


class FindMyReport(Protocol):
    hashed_adv_key_bytes: bytes
    latitude: float
    longitude: float
    horizontal_accuracy: float
    confidence: int
    timestamp: datetime

    def decrypt(self, key_pair: KeyPair) -> None: ...


ReportQuery = tuple[list[str], list[object]]


class AppleFetcher:
    """Fetch and decrypt reports for a batch of tags."""

    def __init__(
        self,
        session: AppleSession,
        alerter: NotificationProvider | None = None,
    ) -> None:
        self._session = session
        self._alerter = alerter

    async def fetch_all(self, tags: list[Tag]) -> dict[str, list[Position]]:
        if not tags:
            return {}

        key_pairs: dict[str, KeyPair] = {}
        tags_by_hashed_key: dict[bytes, Tag] = {}
        queries: list[ReportQuery] = []

        for tag in tags:
            try:
                key_pair = KeyPair(tag.private_key)
            except (TypeError, ValueError):
                logger.exception("Invalid private key for tag %s", tag.id)
                continue
            key_pairs[tag.id] = key_pair
            tags_by_hashed_key[key_pair.hashed_adv_key_bytes] = tag
            queries.append(([key_pair.hashed_adv_key_b64], []))

        if not queries:
            return {tag.id: [] for tag in tags}

        raw_reports = await self._fetch_in_batches(queries)
        positions_by_tag = {tag.id: [] for tag in tags}

        for report in raw_reports:
            tag = tags_by_hashed_key.get(report.hashed_adv_key_bytes)
            if tag is None:
                continue
            position = self._to_position(report, tag, key_pairs[tag.id])
            if position is not None:
                positions_by_tag[tag.id].append(position)

        return positions_by_tag

    async def _fetch_in_batches(
        self,
        queries: Sequence[ReportQuery],
    ) -> list[FindMyReport]:
        reports: list[FindMyReport] = []
        for start in range(0, len(queries), APPLE_BATCH_SIZE):
            batch = queries[start : start + APPLE_BATCH_SIZE]
            reports.extend(await self._fetch_with_retry(batch))
        return reports

    async def _fetch_with_retry(
        self,
        queries: Sequence[ReportQuery],
    ) -> list[FindMyReport]:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            started_at = time.monotonic()
            try:
                async with self._session.anisette_lock:
                    return await asyncio.wait_for(
                        self._session.account.fetch_raw_reports(queries),
                        timeout=_REQUEST_TIMEOUT,
                    )
            except UnauthorizedError:
                logger.error("Apple session expired or unauthorized")
                if self._alerter:
                    await self._alerter.alert_unauthorized()
                break
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = exc
                duration = time.monotonic() - started_at
                logger.warning(
                    "Apple fetch attempt %d/%d failed after %.1fs: %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    duration,
                    type(exc).__name__,
                )
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(
                        _BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    )
            except Exception as exc:
                logger.exception("Unexpected Apple fetch failure; aborting retries")
                raise ReportFetchError("Apple report retrieval failed") from exc

        if last_error is not None:
            raise ReportFetchError(
                "Apple report retrieval failed after retries"
            ) from last_error
        return []

    @staticmethod
    def _to_position(
        report: FindMyReport,
        tag: Tag,
        key_pair: KeyPair,
    ) -> Position | None:
        try:
            report.decrypt(key_pair)
            return Position(
                tag_id=tag.id,
                lat=report.latitude,
                lng=report.longitude,
                accuracy=float(report.horizontal_accuracy),
                confidence=report.confidence,
                timestamp=report.timestamp,
            )
        except Exception:
            # The Find My library exposes several decryption error types.
            # A malformed report must not abort the remaining reports.
            logger.exception("Invalid report for tag %s", tag.id)
            return None
