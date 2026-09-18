"""Apple account authentication and session lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

_SESSION_MAX_AGE = timedelta(hours=23)
_WATCHDOG_INTERVAL = timedelta(minutes=30)


class AppleAccount(Protocol):
    account_name: str

    async def fetch_raw_reports(self, queries: object) -> list[object]: ...

    async def login(self, apple_id: str, apple_password: str) -> object: ...

    def to_json(self, path: Path) -> None: ...

    async def close(self) -> None: ...


AccountLoader = Callable[[Path, Path], AppleAccount]
AccountFactory = Callable[[object], AppleAccount]
ProviderFactory = Callable[[Path], object]


def _load_account(session_file: Path, libs_path: Path) -> AppleAccount:
    from findmy.reports.account import AsyncAppleAccount

    return AsyncAppleAccount.from_json(session_file, anisette_libs_path=libs_path)


def _create_provider(libs_path: Path) -> object:
    from integrations.anisette.provider import create_provider

    return create_provider("local", libs_path=libs_path)


def _create_account(provider: object) -> AppleAccount:
    from findmy.reports.account import AsyncAppleAccount

    return AsyncAppleAccount(provider)


class AppleSession:
    """Manage a persisted Apple account and its refresh watchdog."""

    def __init__(
        self,
        apple_id: str,
        apple_password: str,
        session_file: Path,
        libs_path: Path,
        *,
        account_loader: AccountLoader = _load_account,
        account_factory: AccountFactory = _create_account,
        provider_factory: ProviderFactory = _create_provider,
    ) -> None:
        self._apple_id = apple_id
        self._apple_password = apple_password
        self._session_file = session_file
        self._libs_path = libs_path
        self._account_loader = account_loader
        self._account_factory = account_factory
        self._provider_factory = provider_factory
        self._account: AppleAccount | None = None
        self._connected_at: datetime | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self.anisette_lock = asyncio.Lock()

    @property
    def account(self) -> AppleAccount:
        if self._account is None:
            raise RuntimeError("AppleSession not connected - call to connect first")
        return self._account

    def is_healthy(self) -> bool:
        return bool(
            self._connected_at
            and datetime.now(timezone.utc) - self._connected_at < _SESSION_MAX_AGE
        )

    async def connect(self) -> None:
        if self._account is not None:
            return
        await self._restore_or_login()
        self._patch_http_timeout()
        self._watchdog_task = asyncio.create_task(self._watchdog())

    async def refresh(self) -> None:
        await self._close_account()
        await self._restore_or_login()
        self._patch_http_timeout()

    async def close(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
        await self._close_account()

    async def _close_account(self) -> None:
        if self._account:
            try:
                await self._account.close()
            except Exception:
                logger.exception("Error closing Apple account")
            finally:
                self._account = None
                self._connected_at = None

    def _patch_http_timeout(self) -> None:
        import aiohttp

        http = getattr(self.account, "_http", None)
        if http is None:
            return
        http._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))

    async def _restore_or_login(self) -> None:
        try:
            account = self._account_loader(self._session_file, self._libs_path)
        except FileNotFoundError:
            logger.info("No saved Apple session found — performing full login")
        except Exception:
            logger.exception("Failed to restore Apple session — performing full login")
        else:
            self._set_connected(account)
            logger.info("Apple session restored — logged in as %s", account.account_name)
            return

        account = await self._login()
        self._set_connected(account)
        logger.info("Apple session saved — logged in as %s", account.account_name)

    async def _login(self) -> AppleAccount:
        from findmy.reports.state import LoginState

        provider = self._provider_factory(self._libs_path)
        account = self._account_factory(provider)
        state = await account.login(self._apple_id, self._apple_password)

        if state == LoginState.REQUIRE_2FA:
            await account.close()
            raise RuntimeError("2FA required — run 'make setup' first")
        if state != LoginState.LOGGED_IN:
            await account.close()
            raise RuntimeError(f"Unexpected login state: {state}")

        account.to_json(self._session_file)
        return account

    def _set_connected(self, account: AppleAccount) -> None:
        self._account = account
        self._connected_at = datetime.now(timezone.utc)

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(_WATCHDOG_INTERVAL.total_seconds())
            if self.is_healthy():
                continue
            logger.info("Apple session near expiry — refreshing proactively")
            try:
                await self.refresh()
            except Exception:
                logger.exception("Proactive Apple session refresh failed")
