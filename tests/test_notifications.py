import unittest

from integrations.notifications.provider import NotificationDispatcher


class FakeProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def alert_unauthorized(self) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("notification unavailable")


class NotificationDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_alerts_all_providers_even_when_one_fails(self) -> None:
        failing = FakeProvider(fail=True)
        healthy = FakeProvider()
        dispatcher = NotificationDispatcher([failing, healthy])

        await dispatcher.alert_unauthorized()

        self.assertEqual(failing.calls, 1)
        self.assertEqual(healthy.calls, 1)
