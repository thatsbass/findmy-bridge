import unittest
from datetime import datetime, timezone

from domain.positions.model import Position
from services.publishing import PublishingService


class FakePublisher:
    def __init__(self) -> None:
        self.positions: list[Position] = []

    async def publish(self, position: Position) -> None:
        self.positions.append(position)


def make_position(tag_id: str, hour: int, lat: float) -> Position:
    return Position(
        tag_id=tag_id,
        lat=lat,
        lng=-17.0,
        accuracy=10.0,
        confidence=2,
        timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
    )


class PublishingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_latest_position_and_returns_count(self) -> None:
        publisher = FakePublisher()
        service = PublishingService(publisher)

        count = await service.publish_latest_by_tag(
            {
                "tag-1": [
                    make_position("tag-1", 10, 1.0),
                    make_position("tag-1", 11, 2.0),
                ]
            }
        )

        self.assertEqual(count, 1)
        self.assertEqual(publisher.positions[0].lat, 2.0)

    async def test_does_not_republish_an_old_position(self) -> None:
        publisher = FakePublisher()
        service = PublishingService(publisher)
        positions = {"tag-1": [make_position("tag-1", 11, 2.0)]}

        await service.publish_latest_by_tag(positions)
        count = await service.publish_latest_by_tag(positions)

        self.assertEqual(count, 0)
        self.assertEqual(len(publisher.positions), 1)
