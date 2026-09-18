import unittest
from pathlib import Path

from integrations.apple.session import AppleSession


class FakeAccount:
    account_name = "apple@example.com"

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_restores_account_without_external_dependencies(self) -> None:
        account = FakeAccount()
        session = AppleSession(
            "apple@example.com",
            "password",
            Path("session.json"),
            Path("libs"),
            account_loader=lambda _session_file, _libs_path: account,
        )

        await session._restore_or_login()

        self.assertIs(session.account, account)
        self.assertTrue(session.is_healthy())

    async def test_close_clears_account_and_health_state(self) -> None:
        account = FakeAccount()
        session = AppleSession(
            "apple@example.com",
            "password",
            Path("session.json"),
            Path("libs"),
            account_loader=lambda _session_file, _libs_path: account,
        )

        await session._restore_or_login()
        await session.close()

        self.assertTrue(account.closed)
        self.assertFalse(session.is_healthy())
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            _ = session.account
