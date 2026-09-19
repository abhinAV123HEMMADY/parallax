"""Tutor Match MCP Server (Section 5.2).

Combines pgvector cosine similarity over tutor specialty embeddings with geo radius, price
ceiling, session format, and verification tier — the verification tier is surfaced directly
in the match result rather than hidden behind a separate profile click.
"""

import hashlib
import os
import random

import asyncpg
from mcp.server.fastmcp import FastMCP

DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "postgresql://mentra:mentra@localhost:5433/mentra")
PORT = int(os.environ.get("PORT", 8102))

mcp = FastMCP("tutor-match-mcp", port=PORT)
_pool: asyncpg.Pool | None = None


def pseudo_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic placeholder embedding — see video_transcript/server.py for rationale."""
    seed = int(hashlib.sha256(text.lower().encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


@mcp.tool()
async def find_tutors(
    subject: str,
    topic_query: str,
    location_lat: float | None = None,
    location_lng: float | None = None,
    radius_km: float = 25.0,
    price_max: float | None = None,
    session_format: str | None = None,
    verification_tier: str | None = None,
) -> list[dict]:
    embedding = pseudo_embed(topic_query)

    clauses = ["$2 = ANY(subjects)"]
    params: list = [str(embedding), subject]

    if price_max is not None:
        params.append(price_max)
        clauses.append(f"price_per_hour <= ${len(params)}")
    if session_format is not None:
        params.append(session_format)
        clauses.append(f"(session_format = ${len(params)} OR session_format = 'both')")
    if verification_tier is not None:
        params.append(verification_tier)
        clauses.append(f"verification_tier = ${len(params)}")
    if location_lat is not None and location_lng is not None:
        params.append(location_lat)
        lat_idx = len(params)
        params.append(location_lng)
        lng_idx = len(params)
        params.append(radius_km)
        radius_idx = len(params)
        clauses.append(
            f"""(location_lat IS NULL OR
                 6371 * acos(LEAST(1.0, cos(radians(${lat_idx})) * cos(radians(location_lat)) *
                 cos(radians(location_lng) - radians(${lng_idx})) +
                 sin(radians(${lat_idx})) * sin(radians(location_lat)))) <= ${radius_idx})"""
        )

    where_sql = " AND ".join(clauses)
    query = f"""
        SELECT id, name, subjects, verification_tier, rating, response_time_percentile,
               price_per_hour, session_format,
               1 - (specialty_embedding <=> $1::vector) AS relevance
        FROM tutor_profiles
        WHERE {where_sql}
        ORDER BY specialty_embedding <=> $1::vector
        LIMIT 10
    """

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


@mcp.tool()
async def get_tutor_profile(tutor_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # specialty_embedding is excluded — asyncpg has no codec registered for the pgvector
        # type, so selecting it directly (rather than only using it inside a SQL expression,
        # as find_tutors does) would fail to decode.
        row = await conn.fetchrow(
            """
            SELECT id, name, subjects, location_lat, location_lng, verification_tier,
                   response_time_percentile, rating, price_per_hour, session_format
            FROM tutor_profiles WHERE id = $1
            """,
            tutor_id,
        )
    return dict(row) if row else {}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
