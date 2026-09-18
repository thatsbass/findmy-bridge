import unittest
from contextlib import asynccontextmanager

from infrastructure.database.tags import PostgresTagRepository


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.query: str | None = None

    async def fetch(self, query: str) -> list[dict[str, object]]:
        self.query = query
        return self.rows


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.closed = False

    @asynccontextmanager
    async def acquire(self):
        yield self.connection

    async def close(self) -> None:
        self.closed = True


class TagRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_loads_active_tags_from_database_rows(self) -> None:
        connection = FakeConnection(
            [
                {
                    "id": "tag-1",
                    "private_key": bytearray(b"private"),
                    "advertising_key": bytearray(b"advertising"),
                }
            ]
        )
        pool = FakePool(connection)
        repository = PostgresTagRepository(
            "postgresql://test",
            pool_factory=lambda _dsn: self._pool(pool),
        )

        await repository.connect()
        tags = await repository.load_active_tags()

        self.assertEqual(tags[0].id, "tag-1")
        self.assertEqual(tags[0].private_key, b"private")
        self.assertIn("subscriptions", connection.query or "")

    async def test_requires_connection_before_loading(self) -> None:
        repository = PostgresTagRepository("postgresql://test")

        with self.assertRaisesRegex(RuntimeError, "connect"):
            await repository.load_active_tags()

    async def test_close_closes_pool(self) -> None:
        pool = FakePool(FakeConnection([]))
        repository = PostgresTagRepository(
            "postgresql://test",
            pool_factory=lambda _dsn: self._pool(pool),
        )

        await repository.connect()
        await repository.close()

        self.assertTrue(pool.closed)

    async def _pool(self, pool: FakePool) -> FakePool:
        return pool
