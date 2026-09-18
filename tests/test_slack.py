import unittest

from integrations.notifications.slack import SlackAlerter, SlackTransportError


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeTransport:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.url: str | None = None
        self.payload: dict[str, object] | None = None
        self.closed = False

    async def post(self, url: str, *, json: dict[str, object]) -> FakeResponse:
        self.url = url
        self.payload = json
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def close(self) -> None:
        self.closed = True


class SlackAlerterTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_unauthorized_payload(self) -> None:
        transport = FakeTransport(FakeResponse(204))
        alerter = SlackAlerter("https://hooks.slack.test/secret", transport=transport)

        await alerter.alert_unauthorized()

        self.assertEqual(transport.url, "https://hooks.slack.test/secret")
        self.assertEqual(transport.payload["blocks"][0]["type"], "section")

    async def test_slack_failure_is_absorbed(self) -> None:
        transport = FakeTransport(SlackTransportError("unavailable"))
        alerter = SlackAlerter("https://hooks.slack.test/secret", transport=transport)

        await alerter.alert_unauthorized()

    async def test_closes_transport(self) -> None:
        transport = FakeTransport(FakeResponse(200))
        alerter = SlackAlerter("https://hooks.slack.test/secret", transport=transport)

        await alerter.close()

        self.assertTrue(transport.closed)
