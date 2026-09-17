"""PostgreSQL implementation of TagRepository."""

from __future__ import annotations

import logging

import asyncpg

from domain.models import Tag

logger = logging.getLogger(__name__)


class PostgresTagRepository:
    """Reads tag cryptographic material from PostgreSQL."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        logger.info("PostgreSQL pool created")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL pool closed")

    def _require_pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("PostgresTagRepository.connect() must be called before use")
        return self._pool

    async def load_active_tags(self) -> list[Tag]:
        pool = self._require_pool()

        query = """
            SELECT DISTINCT t.id, t.private_key, t.advertising_key
            FROM tags t
            INNER JOIN subscriptions s ON s.tag_id = t.id
            WHERE t.status = 'assigned'
              AND s.active = true
              AND s.expires_at > NOW()
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

        tags = [
            Tag(
                id=str(row["id"]),
                private_key=bytes(row["private_key"]),
                advertising_key=bytes(row["advertising_key"]),
            )
            for row in rows
        ]
        logger.info("Active tags loaded: %d", len(tags))
        return tags
