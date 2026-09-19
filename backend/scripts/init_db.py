"""Creates the schema against Postgres. Run after `docker compose up -d` and before seed.py."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models import *  # noqa: E402,F401,F403  (registers all models on Base.metadata)


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Schema created.")


if __name__ == "__main__":
    asyncio.run(main())
