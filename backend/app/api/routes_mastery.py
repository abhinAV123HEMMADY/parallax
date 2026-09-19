"""Mastery Map (knowledge graph) endpoint.

Turns the three primitives the platform already tracks — Topics, PrerequisiteEdges, and
MasteryScores — into a *living* graph: mastery is the learned score, but each node also carries
a retrievability computed from the learner's actual flashcard review history via the same FSRS
forgetting curve used for scheduling (Section 4.6). A concept the learner once mastered but
hasn't reviewed decays on the map, which is what makes this a memory model rather than a static
report card.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.fsrs.scheduler import forgetting_curve
from app.models import Flashcard, Lesson, MasteryScore, PrerequisiteEdge, Topic

router = APIRouter(prefix="/mastery", tags=["mastery"])


def _classify(mastery: float, retrievability: float | None, is_prereq: bool, touched: bool) -> str:
    if not touched:
        return "untouched"
    effective = mastery if retrievability is None else mastery * retrievability
    if effective < settings.gap_threshold:
        return "gap" if is_prereq else "weak"
    if retrievability is not None and retrievability < 0.8:
        return "decaying"
    return "mastered"


@router.get("/graph/{user_id}")
async def mastery_graph(user_id: str, db: AsyncSession = Depends(get_db)):
    topics = list((await db.execute(select(Topic))).scalars().all())
    edges = list((await db.execute(select(PrerequisiteEdge))).scalars().all())

    mastery_rows = (
        await db.execute(select(MasteryScore).where(MasteryScore.user_id == user_id))
    ).scalars().all()
    mastery_by_topic = {m.topic_id: m.score for m in mastery_rows}

    # Aggregate retrievability per topic from the learner's own cards (joined via their lessons).
    cards = (
        await db.execute(
            select(Flashcard.stability, Flashcard.elapsed_days, Lesson.topic_id)
            .join(Lesson, Flashcard.lesson_id == Lesson.id)
            .where(Lesson.learner_id == user_id)
        )
    ).all()
    retr_acc: dict[str, list[float]] = {}
    for stability, elapsed_days, topic_id in cards:
        retr_acc.setdefault(topic_id, []).append(forgetting_curve(stability, elapsed_days))
    retrievability_by_topic = {t: sum(v) / len(v) for t, v in retr_acc.items() if v}

    prereq_ids = {e.prerequisite_topic_id for e in edges}  # topics something else depends on

    nodes = []
    for t in topics:
        touched = t.id in mastery_by_topic or t.id in retrievability_by_topic
        mastery = mastery_by_topic.get(t.id, 0.0)
        retr = retrievability_by_topic.get(t.id)
        status = _classify(mastery, retr, t.id in prereq_ids, touched)
        effective = mastery if retr is None else round(mastery * retr, 3)
        nodes.append(
            {
                "id": t.id,
                "name": t.name,
                "subject": t.subject,
                "mastery": round(mastery, 3),
                "retrievability": None if retr is None else round(retr, 3),
                "effective_mastery": effective,
                "status": status,
                "cards_tracked": len(retr_acc.get(t.id, [])),
            }
        )

    summary = {
        "mastered": sum(1 for n in nodes if n["status"] == "mastered"),
        "decaying": sum(1 for n in nodes if n["status"] == "decaying"),
        "gaps": sum(1 for n in nodes if n["status"] in ("gap", "weak")),
        "untouched": sum(1 for n in nodes if n["status"] == "untouched"),
        "overall": round(
            sum(n["effective_mastery"] for n in nodes) / len(nodes), 3
        ) if nodes else 0.0,
    }

    return {
        "nodes": nodes,
        "edges": [{"from": e.prerequisite_topic_id, "to": e.topic_id} for e in edges],
        "summary": summary,
    }
