"""Slack notification integration via Incoming Webhooks."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


class SlackResponse(Protocol):
    status_code: int


class SlackTransport(Protocol):
    async def post(self, url: str, *, json: Mapping[str, object]) -> SlackResponse: ...

    async def close(self) -> None: ...


class SlackTransportError(Exception):
    """A transport-level failure while sending a Slack notification."""


class _HttpxTransport:
    def __init__(self) -> None:
        import httpx

        self._httpx = httpx
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)

    async def post(self, url: str, *, json: Mapping[str, object]) -> SlackResponse:
        try:
            return await self._client.post(url, json=json)
        except self._httpx.RequestError as exc:
            raise SlackTransportError from exc

    async def close(self) -> None:
        await self._client.aclose()


class SlackAlerter:
    """Send authorization alerts without leaking Slack details to the app."""

    def __init__(self, webhook_url: str, *, transport: SlackTransport | None = None) -> None:
        self._webhook_url = webhook_url
        self._transport = transport or _HttpxTransport()

    async def alert_unauthorized(self) -> None:
        try:
            response = await self._transport.post(
                self._webhook_url,
                json=self._build_unauthorized_payload(),
            )
            if not 200 <= response.status_code < 300:
                raise SlackTransportError(f"Slack returned HTTP {response.status_code}")
        except SlackTransportError:
            logger.exception("Failed to send Slack alert")

    async def close(self) -> None:
        await self._transport.close()

    @staticmethod
    def _build_unauthorized_payload() -> dict[str, object]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Apple Find My session expired*\n\n"
                            f"*Time:* {now}\n"
                            "*Error:* `UnauthorizedError` — Apple rejected the session.\n"
                            "*Impact:* Tag positions are no longer retrieved.\n\n"
                            "*Action required:* Run `make setup` on the server to regenerate "
                            "the Apple session (2FA required)."
                        ),
                    },
                }
            ]
        }
