#!/usr/bin/env python3
"""Interactive Apple login and session persistence command."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from config.settings import Config
from findmy.reports.account import AsyncAppleAccount
from findmy.reports.state import LoginState
from integrations.anisette.provider import create_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("findmy_setup")


async def setup() -> None:
    """Log into Apple once and save the session for the worker."""
    config = Config.load()
    session_file = Path(config.apple_session_path)
    libs_path = Path(config.anisette_libs_path)

    try:
        account = AsyncAppleAccount.from_json(
            session_file,
            anisette_libs_path=libs_path,
        )
    except FileNotFoundError:
        account = None
    except Exception:
        logger.exception("Failed to restore the existing Apple session; logging in again")
        account = None

    if account is not None:
        logger.info(
            "Session already exists — logged in as %s (%s %s)",
            account.account_name,
            account.first_name,
            account.last_name,
        )
        logger.info("Delete %s to re-login", session_file)
        await account.close()
        return

    logger.info("Logging in as %s", config.apple_id)
    provider = create_provider(
        config.anisette_provider,
        libs_path=libs_path,
        url=config.anisette_url,
    )
    account = AsyncAppleAccount(provider)
    try:
        state = await account.login(config.apple_id, config.apple_password)
        if state == LoginState.REQUIRE_2FA:
            state = await _complete_two_factor(account)

        if state == LoginState.LOGGED_IN:
            account.to_json(session_file)
            logger.info("Session saved — logged in as %s", account.account_name)
        else:
            logger.error("Login failed: %s", state)
    finally:
        await account.close()


async def _complete_two_factor(account: AsyncAppleAccount) -> LoginState:
    methods = await account.get_2fa_methods()
    logger.info("2FA required. Choose a method:")
    for index, method in enumerate(methods):
        extra = getattr(method, "phone_number", "")
        print(f"  [{index}] {type(method).__name__} {extra}")

    try:
        choice = int(input("\nMethod number: "))
        method = methods[choice]
    except (ValueError, IndexError) as exc:
        raise ValueError("Invalid 2FA method selection") from exc
    await method.request()
    state = await method.submit(input("Enter 2FA code: "))
    return state


if __name__ == "__main__":
    asyncio.run(setup())
