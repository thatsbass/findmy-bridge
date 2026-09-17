#!/usr/bin/env python3
"""One-time setup: logs into Apple account and saves the session.

Run this ONCE before starting the service. After that, the session
will be restored automatically and no 2FA is needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from findmy.reports.account import AsyncAppleAccount
from findmy.reports.anisette import LocalAnisetteProvider
from findmy.reports.state import LoginState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("setup")

SESSION_FILE = Path("account_session.json")
ANISETTE_LIBS_PATH = Path(".anisette_libs")


async def setup() -> None:
    cfg = Config.load()

    try:
        acc = AsyncAppleAccount.from_json(SESSION_FILE, anisette_libs_path=ANISETTE_LIBS_PATH)
        logger.info("Session already exists — logged in as %s (%s %s)", acc.account_name, acc.first_name, acc.last_name)
        logger.info("Delete account_session.json to re-login.")
        await acc.close()
        return
    except Exception:
        pass

    logger.info("Logging in as %s...", cfg.apple_id)
    ani = LocalAnisetteProvider(libs_path=ANISETTE_LIBS_PATH)
    acc = AsyncAppleAccount(ani)
    state = await acc.login(cfg.apple_id, cfg.apple_password)

    if state == LoginState.REQUIRE_2FA:
        methods = await acc.get_2fa_methods()
        logger.info("2FA required. Choose a method:")
        for i, m in enumerate(methods):
            extra = getattr(m, "phone_number", "")
            print(f"  [{i}] {type(m).__name__} {extra}")

        choice = int(input("\nMethod number: "))
        method = methods[choice]
        await method.request()

        code = input("Enter 2FA code: ")
        state = await method.submit(code)

    if state == LoginState.LOGGED_IN:
        acc.to_json(SESSION_FILE)
        logger.info("Session saved — logged in as %s (%s %s)", acc.account_name, acc.first_name, acc.last_name)
    else:
        logger.error("Login failed: %s", state)

    await acc.close()


if __name__ == "__main__":
    asyncio.run(setup())
