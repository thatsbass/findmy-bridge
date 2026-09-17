"""Port interfaces — dependency inversion layer."""

from __future__ import annotations

from typing import Protocol

from domain.models import Position, Tag


class TagRepository(Protocol):
    async def load_active_tags(self) -> list[Tag]: ...


class PositionPublisher(Protocol):
    async def publish(self, position: Position) -> None: ...
    async def close(self) -> None: ...
