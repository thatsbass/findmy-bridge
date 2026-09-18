import unittest
from datetime import datetime, timezone

from domain.positions.model import Position
from domain.tags.model import Tag
from services.polling import PollingService
from services.publishing import PublishingService


class FakeRepository:
    def __init__(self, tags: list[Tag]) -> None:
        self.tags = tags

    async def load_active_tags(self) -> list[Tag]:
        return self.tags


class FakeFetcher:
    def __init__(self, positions_by_tag: dict[str, list[Position]]) -> None:
        self.positions_by_tag = positions_by_tag
        self.received_tags: list[Tag] = []

    async def fetch_all(self, tags: list[Tag]) -> dict[str, list[Position]]:
        self.received_tags = tags
        return self.positions_by_tag


class FakePublisher:
    def __init__(self, failing_tag_id: str | None = None) -> None:
        self.positions: list[Position] = []
        self.failing_tag_id = failing_tag_id

    async def publish(self, position: Position) -> None:
        if position.tag_id == self.failing_tag_id:
            raise RuntimeError("backend unavailable")
        self.positions.append(position)


def make_position(tag_id: str, timestamp: str, lat: float) -> Position:
    return Position(
        tag_id=tag_id,
        lat=lat,
        lng=-17.0,
        accuracy=10.0,
        confidence=2,
        timestamp=datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc),
    )


class PollingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_only_the_freshest_position_per_tag(self) -> None:
        tags = [Tag("tag-1", b"private", b"advertising")]
        fetcher = FakeFetcher(
            {
                "tag-1": [
                    make_position("tag-1", "2026-01-01T10:00:00", 1.0),
                    make_position("tag-1", "2026-01-01T11:00:00", 2.0),
                ]
            }
        )
        publisher = FakePublisher()
        service = PollingService(
            FakeRepository(tags), fetcher, PublishingService(publisher)
        )

        await service.run_cycle()

        self.assertEqual([published.lat for published in publisher.positions], [2.0])
        self.assertEqual(fetcher.received_tags, tags)

    async def test_does_not_republish_a_position_seen_in_a_previous_cycle(self) -> None:
        tags = [Tag("tag-1", b"private", b"advertising")]
        latest = make_position("tag-1", "2026-01-01T11:00:00", 2.0)
        publisher = FakePublisher()
        service = PollingService(
            FakeRepository(tags),
            FakeFetcher({"tag-1": [latest]}),
            PublishingService(publisher),
        )

        await service.run_cycle()
        await service.run_cycle()

        self.assertEqual(len(publisher.positions), 1)

    async def test_publish_failure_does_not_prevent_other_tags(self) -> None:
        tags = [
            Tag("failed", b"private", b"advertising"),
            Tag("ok", b"private", b"advertising"),
        ]
        publisher = FakePublisher(failing_tag_id="failed")
        service = PollingService(
            FakeRepository(tags),
            FakeFetcher(
                {
                    "failed": [make_position("failed", "2026-01-01T11:00:00", 1.0)],
                    "ok": [make_position("ok", "2026-01-01T11:00:00", 2.0)],
                }
            ),
            PublishingService(publisher),
        )

        await service.run_cycle()

        self.assertEqual([published.tag_id for published in publisher.positions], ["ok"])
