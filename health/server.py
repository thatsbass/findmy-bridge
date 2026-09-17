"""Lightweight aiohttp health server."""

from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


class HealthServer:
    def __init__(self, port: int) -> None:
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._handler)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self._port).start()
        logger.info("Health server listening on :%d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handler(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})
