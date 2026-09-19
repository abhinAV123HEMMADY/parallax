"""Peer Insight Engine: struggle feed aggregation and study-squad proposals (Section 7).

Both real, deterministic logic — no LLM call, matching Section 14's "measurable performance,
never inferred from sentiment" constraint.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Connection, StruggleEvent, StudySquad, Topic

SQUAD_THRESHOLD = 3
SQUAD_WINDOW_DAYS = 14
STRUGGLE_SEVERITY_CUTOFF = 0.5


async def _connections_of(db: AsyncSession, user_id: str) -> set[str]:
    result = await db.execute(
        select(Connection).where(
            Connection.status == "connected",
            or_(Connection.user_id_a == user_id, Connection.user_id_b == user_id),
        )
    )
    peers = set()
    for conn in result.scalars().all():
        peers.add(conn.user_id_b if conn.user_id_a == user_id else conn.user_id_a)
    return peers


async def get_struggle_feed(db: AsyncSession, viewer_id: str) -> list[dict]:
    """Aggregated feed items for `viewer_id`'s connections. Exposes relative signal
    ("struggling" vs "on track") only — never a raw severity score (Section 7.2).
    """
    peer_ids = await _connections_of(db, viewer_id)
    if not peer_ids:
        return []

    result = await db.execute(
        select(StruggleEvent, Topic)
        .join(Topic, Topic.id == StruggleEvent.topic_id)
        .where(StruggleEvent.user_id.in_(peer_ids), StruggleEvent.visibility != "private")
    )

    feed = []
    for event, topic in result.all():
        feed.append(
            {
                "user_id": event.user_id,
                "topic_id": topic.id,
                "topic_name": topic.name,
                "relative_signal": "struggling" if event.severity >= STRUGGLE_SEVERITY_CUTOFF else "on_track",
            }
        )
    return feed


async def propose_squads_for_topic(db: AsyncSession, topic_id: str) -> list[dict]:
    """3+ mutually-connected learners with an unresolved struggle signal on the same topic,
    within the recent window, get proposed as a study squad (Section 7.3).
    """
    since = datetime.utcnow() - timedelta(days=SQUAD_WINDOW_DAYS)
    result = await db.execute(
        select(StruggleEvent.user_id)
        .where(
            StruggleEvent.topic_id == topic_id,
            StruggleEvent.created_at >= since,
            StruggleEvent.severity >= STRUGGLE_SEVERITY_CUTOFF,
        )
        .distinct()
    )
    strugglers = {row[0] for row in result.all()}

    proposals = []
    considered: set[str] = set()
    for learner_id in strugglers:
        if learner_id in considered:
            continue
        connected_strugglers = (await _connections_of(db, learner_id)) & strugglers
        group = connected_strugglers | {learner_id}
        if len(group) >= SQUAD_THRESHOLD:
            considered |= group
            proposals.append({"topic_id": topic_id, "member_ids": sorted(group)})

    return proposals


async def persist_squad_proposals(db: AsyncSession, proposals: list[dict]) -> list[StudySquad]:
    squads = []
    for proposal in proposals:
        squad = StudySquad(
            id=str(uuid.uuid4()), topic_id=proposal["topic_id"], member_ids=proposal["member_ids"]
        )
        db.add(squad)
        squads.append(squad)
    await db.commit()
    return squads
