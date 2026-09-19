from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# NullPool — no connections are pooled across calls. Necessary because this engine is shared
# between the FastAPI process (one long-lived event loop) and Celery task nodes, which each
# run inside their own asyncio.run() call and therefore their own event loop; asyncpg
# connections are bound to the loop they were opened on, so a pooled connection reused across
# loops raises "another operation is in progress". NullPool trades a per-query connection
# handshake for correctness — fine at this traffic level.
engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
