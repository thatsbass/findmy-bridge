"""Business rules for working with positions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from domain.exceptions import InvalidPositionError
from domain.positions.model import Position


def latest_position(positions: Sequence[Position]) -> Position:
    """Return the freshest position in a non-empty collection."""
    if not positions:
        raise InvalidPositionError("At least one position is required")
    tag_ids = {position.tag_id for position in positions}
    if len(tag_ids) != 1:
        raise InvalidPositionError("All positions must belong to the same tag")
    return max(positions, key=lambda position: position.timestamp)


def is_newer_than(position: Position, timestamp: datetime | None) -> bool:
    """Return whether a position is newer than a previous timestamp."""
    return timestamp is None or position.timestamp > timestamp
