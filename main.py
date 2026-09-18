"""Find My polling service entry point."""

from __future__ import annotations

import asyncio
import logging

from config.logging_setup import setup_logging
from config.settings import Config
from worker.runner import run_worker

logger = logging.getLogger("findmy_service")


async def main() -> None:
    config = Config.load()
    setup_logging(config)
    logger.info("Find My polling service starting (env=%s)", config.env)
    await run_worker(config)


if __name__ == "__main__":
    asyncio.run(main())
