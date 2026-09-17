"""Provider-agnostic notification contracts and dispatching."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

logger = logging.getLogger(__name__)


class NotificationProvider(Protocol):
    async def alert_unauthorized(self) -> None: ...


class NotificationDispatcher:

    def __init__(self, providers: Sequence[NotificationProvider]) -> None:
        self._providers = tuple(providers)

    async def alert_unauthorized(self) -> None:
        for provider in self._providers:
            try:
                await provider.alert_unauthorized()
            except Exception:
                logger.exception(
                    "Notification provider %s failed",
                    type(provider).__name__,
                )
