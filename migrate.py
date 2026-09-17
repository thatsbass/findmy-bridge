"""Run SQL migration files against the configured database."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()


async def run(sql_file: Path) -> None:
    dsn = os.environ["DATABASE_URL"]
    sql = sql_file.read_text()

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
        print(f"Applied: {sql_file}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python migrate.py <sql_file>")
        sys.exit(1)
    asyncio.run(run(Path(sys.argv[1])))
