import unittest
from datetime import datetime, timezone

from domain.positions.model import Position
from integrations.backend.publisher import (
    BackendPublishError,
    BackendTransportError,
    HttpPositionPublisher,
)


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []
        self.closed = False

    async def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
        self.requests.append({"url": url, "json": json, "headers": headers})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def close(self) -> None:
        self.closed = True


def make_position() -> Position:
    return Position(
        tag_id="tag-1",
        lat=14.7,
        lng=-17.4,
        accuracy=10.0,
        confidence=2,
        timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
    )


class PublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_serializes_and_publishes_position(self) -> None:
        transport = FakeTransport([FakeResponse(201)])
        publisher = HttpPositionPublisher("http://backend/", "secret", transport=transport)

        await publisher.publish(make_position())

        request = transport.requests[0]
        self.assertEqual(request["url"], "http://backend/api/internal/positions")
        self.assertEqual(request["json"]["tag_id"], "tag-1")
        self.assertEqual(request["headers"]["X-API-Key"], "secret")

    async def test_retries_server_error_and_then_succeeds(self) -> None:
        transport = FakeTransport([FakeResponse(503), FakeResponse(200)])
        delays: list[float] = []

        async def sleep(delay: float) -> None:
            delays.append(delay)

        publisher = HttpPositionPublisher(
            "http://backend",
            "secret",
            transport=transport,
            sleep=sleep,
        )

        await publisher.publish(make_position())

        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(delays, [1.0])

    async def test_does_not_retry_client_error(self) -> None:
        transport = FakeTransport([FakeResponse(400)])
        publisher = HttpPositionPublisher("http://backend", "secret", transport=transport)

        with self.assertRaises(BackendPublishError) as raised:
            await publisher.publish(make_position())

        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(raised.exception.status_code, 400)

    async def test_retries_transport_failure_up_to_limit(self) -> None:
        transport = FakeTransport(
            [BackendTransportError(), BackendTransportError(), BackendTransportError()]
        )
        delays: list[float] = []

        async def sleep(delay: float) -> None:
            delays.append(delay)

        publisher = HttpPositionPublisher(
            "http://backend",
            "secret",
            transport=transport,
            sleep=sleep,
        )

        with self.assertRaises(BackendPublishError) as raised:
            await publisher.publish(make_position())

        self.assertEqual(raised.exception.attempts, 3)
        self.assertEqual(delays, [1.0, 4.0])

    async def test_closes_injected_transport(self) -> None:
        transport = FakeTransport([])
        publisher = HttpPositionPublisher("http://backend", "secret", transport=transport)

        await publisher.close()

        self.assertTrue(transport.closed)
