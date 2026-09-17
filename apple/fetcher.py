"""Fetches and decrypts Apple Find My reports for a batch of tags."""

from __future__ import annotations

import asyncio
import logging
import random
import time

import aiohttp
from findmy.errors import UnauthorizedError
from findmy.keys import KeyPair

from apple.session import AppleSession
from domain.models import Position, Tag
from notifications.provider import NotificationProvider

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_BACKOFF = 2.0      # seconds — doubles each retry: 2s, 4s (+jitter)
_REQUEST_TIMEOUT = 60.0  # outer safety net per attempt (aiohttp internal may fire sooner)
APPLE_BATCH_SIZE = 500   # max queries per fetch_raw_reports call — move to Config when needed


class AppleFetcher:
    """Fetches all tags in a single Apple API call, decrypts locally."""

    def __init__(
        self,
        session: AppleSession,
        alerter: NotificationProvider | None = None,
    ) -> None:
        self._session = session
        self._alerter = alerter

    async def fetch_all(self, tags: list[Tag]) -> dict[str, list[Position]]:
        """
        One HTTP call + one Anisette invocation for all tags combined.
        Queries are split into chunks of APPLE_BATCH_SIZE. Each chunk is fetched
        independently with retry. Reports are matched via hashed_adv_key_bytes (O(1)).
        """
        if not tags:
            return {}
        """
        KeyPair derives the advertising key from the private key (P-224 EC).
        hashed_adv_key_bytes = SHA-256(adv_key) — used both as Apple API lookup key
        and to match incoming reports back to their tag in O(1).
        """
        key_pairs: dict[str, KeyPair] = {
            tag.id: KeyPair(tag.private_key) for tag in tags
        }
        hashed_key_to_tag: dict[bytes, Tag] = {
            key_pairs[tag.id].hashed_adv_key_bytes: tag for tag in tags
        }
        queries = [
            ([kp.hashed_adv_key_b64], [])
            for kp in key_pairs.values()
        ]

        raw_reports = await self._fetch_with_retry(queries)

        results: dict[str, list[Position]] = {tag.id: [] for tag in tags}
        decrypted = 0
        skipped = 0

        for report in raw_reports:
            tag = hashed_key_to_tag.get(report.hashed_adv_key_bytes)
            if not tag:
                continue

            try:
                report.decrypt(key_pairs[tag.id])
            except Exception:
                logger.exception("Failed to decrypt report for tag %s", tag.id)
                skipped += 1
                continue

            results[tag.id].append(
                Position(
                    tag_id=tag.id,
                    lat=report.latitude,
                    lng=report.longitude,
                    accuracy=float(report.horizontal_accuracy),
                    confidence=report.confidence,
                    timestamp=report.timestamp,
                )
            )
            decrypted += 1

        if raw_reports:
            logger.info(
                "Batch fetch complete — %d raw / %d decrypted / %d skipped — %d tags",
                len(raw_reports), decrypted, skipped, len(tags),
            )
        return results

    async def _fetch_with_retry(self, queries: list) -> list:
        """
        Split queries into chunks and fetch each with retry.
        Chunking is a no-op for small fleets (one chunk). For large fleets each
        chunk is retried independently, preventing a single slow chunk from
        blocking all others.
        """
        chunks = [
            queries[i: i + APPLE_BATCH_SIZE]
            for i in range(0, len(queries), APPLE_BATCH_SIZE)
        ]
        all_reports: list = []
        for chunk in chunks:
            reports = await self._attempt_fetch(chunk, batch_size=len(chunk))
            all_reports.extend(reports)
        return all_reports

    async def _attempt_fetch(self, queries: list, batch_size: int) -> list:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            logger.info(
                "Fetch attempt %d/%d — batch size %d",
                attempt, _MAX_ATTEMPTS, batch_size,
            )
            try:
                logger.debug("Acquiring anisette_lock (attempt %d)", attempt)
                async with self._session.anisette_lock:
                    logger.debug("anisette_lock acquired")
                    raw_reports = await asyncio.wait_for(
                        self._session.account.fetch_raw_reports(queries),
                        timeout=_REQUEST_TIMEOUT,
                    )
                logger.debug("anisette_lock released")
                duration = time.monotonic() - t0
                logger.info(
                    "Fetch succeeded — attempt %d/%d, %d tags, %.1fs",
                    attempt, _MAX_ATTEMPTS, batch_size, duration,
                )
                return raw_reports
            except UnauthorizedError:
                duration = time.monotonic() - t0
                logger.error(
                    "Apple session expired or unauthorized after %.1fs — aborting retries",
                    duration,
                )
                if self._alerter:
                    await self._alerter.alert_unauthorized()
                break
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                duration = time.monotonic() - t0
                logger.warning(
                    "Fetch attempt %d/%d failed after %.1fs — %s",
                    attempt, _MAX_ATTEMPTS, duration, type(exc).__name__,
                )
                if attempt < _MAX_ATTEMPTS:
                    backoff = (_BASE_BACKOFF * (2 ** (attempt - 1))) + random.uniform(0, 1)
                    logger.info("Retrying in %.1fs", backoff)
                    await asyncio.sleep(backoff)
            except Exception:
                duration = time.monotonic() - t0
                logger.exception(
                    "Unexpected error on fetch attempt %d/%d after %.1fs — aborting retries",
                    attempt, _MAX_ATTEMPTS, duration,
                )
                break

        logger.error(
            "All %d fetch attempts failed — batch of %d tags skipped",
            _MAX_ATTEMPTS, batch_size,
        )
        return []
