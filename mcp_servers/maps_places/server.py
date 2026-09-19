"""Maps / Places MCP Server (Section 5.4).

Kept as its own server (rather than folded into Tutor Match) so the geo lookup can later be
swapped for Google Places / Apple Maps without touching matching logic. For this scaffold it
queries tutor_profiles' seeded lat/lng directly instead of a real maps API.
"""

import os

import asyncpg
from mcp.server.fastmcp import FastMCP

DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "postgresql://mentra:mentra@localhost:5433/mentra")
PORT = int(os.environ.get("PORT", 8104))

mcp = FastMCP("maps-places-mcp", port=PORT)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


@mcp.tool()
async def nearby_tutors(lat: float, lng: float, radius_km: float = 25.0) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH distances AS (
                SELECT id, name, subjects, location_lat, location_lng,
                       6371 * acos(LEAST(1.0, cos(radians($1)) * cos(radians(location_lat)) *
                       cos(radians(location_lng) - radians($2)) +
                       sin(radians($1)) * sin(radians(location_lat)))) AS distance_km
                FROM tutor_profiles
                WHERE location_lat IS NOT NULL AND location_lng IS NOT NULL
            )
            SELECT * FROM distances WHERE distance_km <= $3 ORDER BY distance_km
            """,
            lat,
            lng,
            radius_km,
        )
    return [dict(row) for row in rows]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
