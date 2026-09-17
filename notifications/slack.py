"""Slack alerting via Incoming Webhooks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


class SlackAlerter:
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def alert_unauthorized(self) -> None:
        """Send a Slack alert when the Apple session is expired/unauthorized."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        payload = {
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
                            "*Action required:* Run `make setup` on the server to regenerate the Apple session (2FA required)."
                        ),
                    },
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.exception("Failed to send Slack alert")
