"""Apply one SQL migration file to the configured PostgreSQL database."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def apply_migration(sql_file: Path) -> None:
    """Execute the supplied SQL file against DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Missing required environment variable: DATABASE_URL")

    sql = sql_file.read_text(encoding="utf-8")
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(sql)
        print(f"Applied: {sql_file}")
    finally:
        await connection.close()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m cli.migrate <sql_file>")
        raise SystemExit(1)
    asyncio.run(apply_migration(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
