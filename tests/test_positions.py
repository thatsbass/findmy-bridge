import unittest
from datetime import datetime, timezone

from domain.positions.model import Position
from domain.exceptions import InvalidPositionError
from domain.positions import is_newer_than, latest_position


def make_position(hour: int) -> Position:
    return Position(
        tag_id="tag-1",
        lat=1.0,
        lng=-17.0,
        accuracy=10.0,
        confidence=2,
        timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
    )


class PositionRulesTests(unittest.TestCase):
    def test_selects_latest_position(self) -> None:
        older = make_position(10)
        latest = make_position(11)

        self.assertIs(latest_position([older, latest]), latest)

    def test_rejects_empty_position_collection(self) -> None:
        with self.assertRaisesRegex(InvalidPositionError, "At least one"):
            latest_position([])

    def test_rejects_positions_from_different_tags(self) -> None:
        with self.assertRaisesRegex(InvalidPositionError, "same tag"):
            latest_position([make_position(10), Position(
                tag_id="tag-2",
                lat=1.0,
                lng=-17.0,
                accuracy=10.0,
                confidence=2,
                timestamp=make_position(11).timestamp,
            )])

    def test_compares_position_to_last_published_timestamp(self) -> None:
        latest = make_position(11)
        previous = make_position(10).timestamp

        self.assertTrue(is_newer_than(latest, previous))
        self.assertFalse(is_newer_than(latest, latest.timestamp))
        self.assertTrue(is_newer_than(latest, None))
