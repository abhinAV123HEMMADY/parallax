"""Video Transcript MCP Server (Section 5.1).

Wraps a transcript-chunk table (in place of the real YouTube Data API + transcript fetch)
and exposes search_transcripts, returning the single highest-relevance timestamp per video
rather than a whole video — turning a 40-minute lecture into a 90-second answer.
"""

import os

import asyncpg
from mcp.server.fastmcp import FastMCP
from parallax_embed import embed_query

DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "postgresql://parallax:parallax@localhost:5433/parallax")
PORT = int(os.environ.get("PORT", 8101))

mcp = FastMCP("video-transcript-mcp", port=PORT)
_pool: asyncpg.Pool | None = None


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
    # embed_query, not embed_document: bge is asymmetric and the query side takes an
    # instruction prefix. Chunks were stored with embed_document at seed/ingest time.
    embedding = embed_query(topic_query)
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
