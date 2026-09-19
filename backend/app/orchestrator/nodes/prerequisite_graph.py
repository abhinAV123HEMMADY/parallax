from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import MasteryScore, PrerequisiteEdge, Topic
from app.orchestrator.state import LearningState


async def _upstream_of(db, topic_id: str) -> list[Topic]:
    result = await db.execute(
        select(Topic)
        .join(PrerequisiteEdge, PrerequisiteEdge.prerequisite_topic_id == Topic.id)
        .where(PrerequisiteEdge.topic_id == topic_id)
    )
    return list(result.scalars().all())


async def _get_mastery(db, learner_id: str, topic_id: str) -> float:
    result = await db.execute(
        select(MasteryScore).where(
            MasteryScore.user_id == learner_id, MasteryScore.topic_id == topic_id
        )
    )
    row = result.scalars().first()
    return row.score if row else 0.0


async def prerequisite_graph_node(state: LearningState) -> dict:
    """Walks upstream prerequisite edges; redirects the lesson target to the first gap found.

    Real logic (Section 4.2) — deterministic, no LLM call: if the learner's mastery on an
    upstream node is below GAP_THRESHOLD, the lesson target becomes that prerequisite instead
    of the originally requested topic, and the original topic is flagged as blocked-on-gap.
    """
    objectives = dict(state["parsed_objectives"])
    topic_id = objectives["topic_id"]
    learner_id = state["learner_id"]

    prerequisite_gap = None

    # A localized error from a snapped photo is a stronger signal than graph traversal:
    # the vision diagnosis names the exact prerequisite the mistake revealed, so redirect
    # straight to it rather than to the nearest upstream node below threshold.
    diagnosed_id = (state.get("error_analysis") or {}).get("prerequisite_topic_id")
    if diagnosed_id and diagnosed_id != topic_id:
        async with async_session() as db:
            diagnosed = await db.get(Topic, diagnosed_id)
        if diagnosed is not None:
            objectives["topic_id"] = diagnosed.id
            objectives["topic_name"] = diagnosed.name
            objectives["subject"] = diagnosed.subject
            objectives["blocked_on_gap"] = topic_id
            return {"parsed_objectives": objectives, "prerequisite_gap": diagnosed.id}

    async with async_session() as db:
        for prereq in await _upstream_of(db, topic_id):
            mastery = await _get_mastery(db, learner_id, prereq.id)
            if mastery < settings.gap_threshold:
                prerequisite_gap = prereq.id
                objectives["topic_id"] = prereq.id
                objectives["topic_name"] = prereq.name
                objectives["subject"] = prereq.subject
                objectives["blocked_on_gap"] = topic_id
                break

    return {
        "parsed_objectives": objectives,
        "prerequisite_gap": prerequisite_gap,
    }
