"""Apple session lifecycle — authentication, persistence, 24h watchdog."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp

from findmy.reports.account import AsyncAppleAccount
from findmy.reports.anisette import LocalAnisetteProvider
from findmy.reports.state import LoginState

logger = logging.getLogger(__name__)

_SESSION_MAX_AGE = timedelta(hours=23)
_WATCHDOG_INTERVAL = timedelta(minutes=30)


class AppleSession:
    def __init__(
        self,
        apple_id: str,
        apple_password: str,
        session_file: Path,
        libs_path: Path,
    ) -> None:
        self._apple_id = apple_id
        self._apple_password = apple_password
        self._session_file = session_file
        self._libs_path = libs_path
        self._account: AsyncAppleAccount | None = None
        self._connected_at: datetime | None = None
        self._watchdog_task: asyncio.Task | None = None
        """
        Unicorn (ARM64 emulator used by Anisette) is not thread-safe.
        This lock serializes all fetch_raw_reports calls to prevent concurrent
        access to the emulator, which causes UC_ERR_WRITE_UNMAPPED / segfault.
        """
        self.anisette_lock = asyncio.Lock()

    @property
    def account(self) -> AsyncAppleAccount:
        if not self._account:
            raise RuntimeError("AppleSession not connected - call to connect first")
        return self._account

    def is_healthy(self) -> bool:
        if not self._connected_at:
            return False
        return datetime.now(timezone.utc) - self._connected_at < _SESSION_MAX_AGE

    async def connect(self) -> None:
        await self._restore_or_login()
        self._patch_http_timeout()
        self._watchdog_task = asyncio.create_task(self._watchdog())

    async def refresh(self) -> None:
        if self._account:
            try:
                await self._account.close()
            except Exception:
                logger.exception("Error closing account before refresh")
            self._account = None
        await self._restore_or_login()
        self._patch_http_timeout()

    async def close(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass

        if self._account:
            try:
                await self._account.close()
            except Exception:
                logger.exception("Error closing Apple account")

    def _patch_http_timeout(self) -> None:
        """
        findmy.util.http.HttpSession hard-codes ClientTimeout(total=5).
        Pre-seeding _session with our own ClientSession forces _get_session()
        to return it on the first call, bypassing the 5 s hardcoded value.
        """
        self._account._http._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
        )
        logger.debug("findmy HTTP timeout patched to 60s")

    async def _restore_or_login(self) -> None:
        try:
            acc = AsyncAppleAccount.from_json(self._session_file, anisette_libs_path=self._libs_path)
            logger.info("Session restored — logged in as %s", acc.account_name)
            self._account = acc
            self._connected_at = datetime.now(timezone.utc)
            return
        except FileNotFoundError:
            logger.info("No saved session found — performing full login")
        except Exception:
            logger.exception("Failed to restore session — performing full login")

        ani = LocalAnisetteProvider(libs_path=self._libs_path)
        acc = AsyncAppleAccount(ani)
        state = await acc.login(self._apple_id, self._apple_password)

        if state == LoginState.REQUIRE_2FA:
            await acc.close()
            raise RuntimeError("2FA required — run 'make setup' first")

        if state != LoginState.LOGGED_IN:
            await acc.close()
            raise RuntimeError(f"Unexpected login state: {state}")

        acc.to_json(self._session_file)
        logger.info("Session saved — logged in as %s", acc.account_name)
        self._account = acc
        self._connected_at = datetime.now(timezone.utc)

    async def _watchdog(self) -> None:
        interval = _WATCHDOG_INTERVAL.total_seconds()
        while True:
            await asyncio.sleep(interval)
            if not self.is_healthy():
                logger.info("Session near expiry — refreshing proactively")
                try:
                    await self.refresh()
                except Exception:
                    logger.exception("Proactive session refresh failed")
