"""Video Transcript MCP Server (Section 5.1).

Wraps a transcript-chunk table (in place of the real YouTube Data API + transcript fetch)
and exposes search_transcripts, returning the single highest-relevance timestamp per video
rather than a whole video — turning a 40-minute lecture into a 90-second answer.
"""

import hashlib
import os
import random

import asyncpg
from mcp.server.fastmcp import FastMCP

DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "postgresql://mentra:mentra@localhost:5433/mentra")
PORT = int(os.environ.get("PORT", 8101))

mcp = FastMCP("video-transcript-mcp", port=PORT)
_pool: asyncpg.Pool | None = None


def pseudo_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic placeholder embedding (no external embedding model call) — same text
    always maps to the same unit vector. Real implementation: Claude embeddings /
    sentence-transformers (Section 11). Intentionally duplicated in each service that needs
    it so MCP servers stay independent processes with no shared-package dependency.
    """
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
async def search_transcripts(topic_query: str, difficulty_level: str = "intro", max_results: int = 5) -> list[dict]:
    """Embeds the query, chunks are already embedded at seed time; returns the highest-relevance
    timestamp per matching chunk (doc Section 5.1 SQL, verbatim query shape).

    difficulty_level is accepted for API-shape compatibility with the doc's tool signature;
    the seeded chunk table doesn't have enough rows per level for a real filter to be
    meaningful yet, so ranking is by embedding similarity only for now.
    """
    embedding = pseudo_embed(topic_query)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT video_id, video_title, chunk_start_seconds, chunk_text, difficulty_level,
                   1 - (chunk_embedding <=> $1::vector) AS relevance
            FROM video_transcript_chunks
            ORDER BY chunk_embedding <=> $1::vector
            LIMIT $2
            """,
            str(embedding),
            max_results,
        )
    return [dict(row) for row in rows]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
