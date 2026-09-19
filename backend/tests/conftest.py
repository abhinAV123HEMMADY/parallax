"""Test fixtures.

Tests run against the real Postgres from docker-compose, inside a transaction that is always
rolled back. That choice over a separate test database is deliberate: the schema here uses
pgvector columns and Postgres-specific constructs (`ARRAY`, `on_conflict_do_update`), so a SQLite
substitute would test different behaviour than production. Rolling back gives isolation without a
second database to keep in sync.

Nothing here commits to the shared dev data. Each test gets a session bound to a connection whose
outer transaction is rolled back on teardown, so even code under test calling `session.commit()`
only commits a nested savepoint.
"""

import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from app.database import engine  # noqa: E402
from app.models import PrerequisiteEdge, Topic, User  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """One loop for the session. The engine uses NullPool and asyncpg binds connections to the
    loop that opened them, so a per-test loop would strand them."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db():
    """An AsyncSession whose work is discarded.

    `join_transaction_mode="create_savepoint"` is what makes this work with code under test that
    commits: the session's commits land on a savepoint inside the outer transaction, and the outer
    rollback still throws everything away.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    maker = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session: AsyncSession = maker()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db):
    """HTTP client with the app's database dependency pointed at the rollback session."""
    from app.database import get_db
    from app.main import app

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def learner(db) -> User:
    """A learner unique to this test, so tests can't interfere via shared seeded rows."""
    user = User(id=f"u_test_{uuid.uuid4().hex[:8]}", name="Test Learner", grade_level="12", goals=[])
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def topic_chain(db) -> list[Topic]:
    """Three topics in a prerequisite chain: basics <- middle <- advanced.

    Ids are randomised because the seeded graph already owns names like "limits", and a fixed id
    would collide with it on the second run.
    """
    suffix = uuid.uuid4().hex[:8]
    topics = [
        Topic(id=f"t_basics_{suffix}", name=f"test basics {suffix}", subject="math"),
        Topic(id=f"t_middle_{suffix}", name=f"test middle {suffix}", subject="math"),
        Topic(id=f"t_advanced_{suffix}", name=f"test advanced {suffix}", subject="math"),
    ]
    for topic in topics:
        db.add(topic)
    await db.flush()

    db.add(PrerequisiteEdge(topic_id=topics[1].id, prerequisite_topic_id=topics[0].id))
    db.add(PrerequisiteEdge(topic_id=topics[2].id, prerequisite_topic_id=topics[1].id))
    await db.flush()
    return topics
