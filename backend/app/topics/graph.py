"""Prerequisite-graph traversal, shared by gap redirection and note ordering.

This module exists because two callers needed the same walk and only one of them had it:
`orchestrator/nodes/prerequisite_graph.py` carried a private one-hop `_upstream_of`, and
nothing anywhere computed depth. Rather than duplicate a second traversal for note ordering,
both now come from here.

Every traversal carries a visited set. `PrerequisiteEdge` is a plain two-column table with no
constraint preventing a cycle (A requires B requires A), so a seed file or a future authoring
UI can introduce one; an unguarded walk would then spin forever inside a request.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PrerequisiteEdge, Topic

# A cycle is already handled by the visited set; this is a second bound against a pathological
# graph making a single request walk thousands of edges.
MAX_DEPTH = 32


async def upstream_of(db: AsyncSession, topic_id: str) -> list[Topic]:
    """Immediate prerequisites of `topic_id` — the topics that must be mastered first."""
    result = await db.execute(
        select(Topic)
        .join(PrerequisiteEdge, PrerequisiteEdge.prerequisite_topic_id == Topic.id)
        .where(PrerequisiteEdge.topic_id == topic_id)
    )
    return list(result.scalars().all())


async def topic_depth(db: AsyncSession, topic_id: str) -> int:
    """How many prerequisite hops deep a topic sits: 0 for a topic with no prerequisites.

    Used to order a course pack so foundations come before what they unlock, rather than
    ordering by whenever the learner happened to watch each video. BFS over the reverse edges,
    taking the longest path, because a topic is only as deep as its deepest prerequisite.
    """
    visited: set[str] = {topic_id}
    frontier = [topic_id]
    depth = 0

    while frontier and depth < MAX_DEPTH:
        next_ids = (
            (
                await db.execute(
                    select(PrerequisiteEdge.prerequisite_topic_id).where(
                        PrerequisiteEdge.topic_id.in_(frontier)
                    )
                )
            )
            .scalars()
            .all()
        )
        frontier = [tid for tid in set(next_ids) if tid not in visited]
        if not frontier:
            break
        visited.update(frontier)
        depth += 1

    return depth


async def depths_for(db: AsyncSession, topic_ids: list[str]) -> dict[str, int]:
    """Depth for several topics at once. Callers sorting a list want every depth, and doing it
    here keeps the N round-trips in one place where a single-query rewrite can replace them."""
    return {topic_id: await topic_depth(db, topic_id) for topic_id in dict.fromkeys(topic_ids)}
