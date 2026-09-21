#!/usr/bin/env bash
# Single-container launcher for hosted deploys (Render/Railway/Fly): runs the four MCP
# servers, initializes/seeds the database once, and starts the Celery worker + API in one
# process tree. Locally the Makefile still runs each piece separately.
set -euo pipefail

# The platform provides one DATABASE_URL (postgres://...). Derive the three dialects the
# app expects: asyncpg for the API, psycopg for sync scripts, plain for the MCP servers.
RAW_DB_URL="${DATABASE_URL:?DATABASE_URL is required}"
BASE_DB_URL="$(printf '%s' "$RAW_DB_URL" | sed -E 's#^postgres(ql)?://#postgresql://#')"

# Hosted Postgres (Neon, Supabase) hands out a libpq URL carrying sslmode= and often
# channel_binding=. Those are fine for psycopg and for raw asyncpg, which parse a DSN — but
# SQLAlchemy's asyncpg dialect forwards unknown query parameters as connect() keyword
# arguments, so the same URL dies with "connect() got an unexpected keyword argument
# 'sslmode'" the moment the API opens a connection. asyncpg spells it ssl= instead.
ASYNC_DB_URL="$(printf '%s' "$BASE_DB_URL" | sed -E 's#[?&](sslmode|channel_binding)=[^&]*##g')"
case "$BASE_DB_URL" in
  # Only re-add TLS if the provider asked for it; a plain local postgres:// must stay plain.
  *sslmode=require*|*sslmode=verify*)
    case "$ASYNC_DB_URL" in
      *\?*) ASYNC_DB_URL="${ASYNC_DB_URL}&ssl=require" ;;
      *)    ASYNC_DB_URL="${ASYNC_DB_URL}?ssl=require" ;;
    esac
    ;;
esac

export DATABASE_URL="${ASYNC_DB_URL/postgresql:\/\//postgresql+asyncpg://}"
export DATABASE_URL_SYNC="${BASE_DB_URL/postgresql:\/\//postgresql+psycopg://}"
export MCP_DATABASE_URL="$BASE_DB_URL"

# MCP servers listen on container-local ports; the orchestrator reaches them via the
# VIDEO/TUTOR/CALENDAR/MAPS_MCP_URL defaults (localhost:8101-8104).
(cd /app/mcp_servers/video_transcript && PORT=8101 python server.py) &
(cd /app/mcp_servers/tutor_match && PORT=8102 python server.py) &
(cd /app/mcp_servers/calendar_booking && PORT=8103 python server.py) &
(cd /app/mcp_servers/maps_places && PORT=8104 python server.py) &

cd /app/backend

python scripts/init_db.py

# Seed only on first boot — seed.py is not idempotent, so guard on the topics table.
python - <<'PY'
import asyncio
import subprocess

from sqlalchemy import text

from app.database import engine


async def topic_count() -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT count(*) FROM topics"))).scalar() or 0


if asyncio.run(topic_count()) == 0:
    print("Empty database — seeding demo data.")
    subprocess.run(["python", "scripts/seed.py"], check=True)
else:
    print("Database already seeded — skipping.")
PY

# solo pool keeps the worker to a single process — the free tiers this targets have tight
# memory, and lesson generation is bursty, not concurrent.
celery -A app.celery_app worker --loglevel=info --pool=solo &

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
