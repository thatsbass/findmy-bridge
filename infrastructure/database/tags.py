"""PostgreSQL repository for active tags."""

from __future__ import annotations

import logging
from collections.abc import AsyncContextManager, Awaitable, Callable, Mapping, Sequence
from typing import Protocol

import asyncpg

from domain.exceptions import RepositoryError
from domain.tags.model import Tag

logger = logging.getLogger(__name__)

_ACTIVE_TAGS_QUERY = """
    SELECT DISTINCT t.id, t.private_key, t.advertising_key
    FROM tags t
    INNER JOIN subscriptions s ON s.tag_id = t.id
    WHERE t.status = 'assigned'
      AND s.active = true
      AND s.expires_at > NOW()
"""


class TagConnection(Protocol):
    async def fetch(self, query: str) -> Sequence[Mapping[str, object]]: ...


class DatabasePool(Protocol):
    def acquire(self) -> AsyncContextManager[TagConnection]: ...

    async def close(self) -> None: ...


PoolFactory = Callable[[str], Awaitable[DatabasePool]]


async def _create_pool(dsn: str) -> DatabasePool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=5)


class PostgresTagRepository:
    """Load active tag cryptographic material from PostgreSQL."""

    def __init__(
        self,
        dsn: str,
        *,
        pool_factory: PoolFactory = _create_pool,
    ) -> None:
        self._dsn = dsn
        self._pool_factory = pool_factory
        self._pool: DatabasePool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        try:
            self._pool = await self._pool_factory(self._dsn)
        except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
            logger.exception("Failed to connect to PostgreSQL")
            raise RepositoryError("Could not connect to PostgreSQL") from exc

        logger.info("PostgreSQL pool created")

    async def close(self) -> None:
        pool = self._pool
        self._pool = None
        if pool is None:
            return

        try:
            await pool.close()
        except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
            logger.exception("Failed to close PostgreSQL pool")
            raise RepositoryError("Could not close PostgreSQL pool") from exc

        logger.info("PostgreSQL pool closed")

    async def load_active_tags(self) -> list[Tag]:
        try:
            pool = self._require_pool()
            async with pool.acquire() as connection:
                rows = await connection.fetch(_ACTIVE_TAGS_QUERY)
            tags = [self._to_tag(row) for row in rows]
        except RepositoryError:
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
            logger.exception("Failed to load active tags from PostgreSQL")
            raise RepositoryError("Could not load active tags") from exc

        logger.info("Active tags loaded: %d", len(tags))
        return tags

    @staticmethod
    def _to_tag(row: Mapping[str, object]) -> Tag:
        try:
            tag_id = str(row["id"])
            private_key = PostgresTagRepository._key_bytes(row["private_key"])
            advertising_key = PostgresTagRepository._key_bytes(row["advertising_key"])
        except KeyError as exc:
            raise RepositoryError("PostgreSQL returned an invalid tag row") from exc

        return Tag(
            id=tag_id,
            private_key=private_key,
            advertising_key=advertising_key,
        )

    @staticmethod
    def _key_bytes(value: object) -> bytes:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise RepositoryError("PostgreSQL returned an invalid tag key")
        return bytes(value)

    def _require_pool(self) -> DatabasePool:
        if self._pool is None:
            raise RuntimeError("PostgresTagRepository.connect() must be called before use")
        return self._pool
