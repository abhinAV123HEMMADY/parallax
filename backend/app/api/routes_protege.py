import json
import logging
import re
import uuid

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.llm import llm_enabled
from app.mastery.service import recompute_mastery
from app.models import ProtegeConcession, ProtegeRecap, ProtegeSession, QnaPost, Topic
from app.moderation.service import moderate_text
from app.orchestrator.nodes.misconception_generator import generate_misconceptions, is_generic_set
from app.orchestrator.nodes.protege_persona import protege_persona_node
from app.orchestrator.nodes.session_recap import write_session_recap
from app.orchestrator.protege_graph import protege_graph
from app.realtime import channel_name
from app.schemas.protege import (
    ChecklistItem,
    ProtegePublishRequest,
    ProtegeRecapResult,
    ProtegeStartRequest,
    ProtegeTurnRequest,
    ProtegeTurnResult,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/protege", tags=["protege"])

UNDERSTANDING_THRESHOLD = 0.75


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _resolve_topic(db: AsyncSession, topic_name: str) -> Topic:
    """Any topic can drive Protégé Mode, not just the ones seeded with a hand-written
    misconception set (Section 9.1) — resolve-or-create the topic row by the same slug
    convention the main pipeline's intent parser uses, then generate-and-cache its
    misconceptions on first use so later sessions on the same topic reuse them.
    """
    topic_id = _slugify(topic_name)
    topic = await db.get(Topic, topic_id)
    if topic is None:
        topic = Topic(id=topic_id, name=topic_name.strip().lower(), subject="general")
        db.add(topic)
        await db.flush()

    # Regenerate when empty — and also when the cached set is the keyless generic template
    # but a live LLM is now available, so topics first touched before the key was configured
    # heal into real, topic-specific misconceptions.
    if not topic.common_misconceptions or (llm_enabled() and is_generic_set(topic.common_misconceptions)):
        topic.common_misconceptions = await generate_misconceptions(topic.name, topic.subject)
        await db.flush()

    return topic


def _checklist_items(misconceptions: list[dict], checklist: dict[str, bool]) -> list[ChecklistItem]:
    return [
        ChecklistItem(id=m["id"], sub_concept=m["sub_concept"], covered=checklist.get(m["id"], False))
        for m in misconceptions
    ]


async def _write_recap(db, session, topic, misconceptions: list[dict], merged: dict) -> None:
    """Write the session's recap once, on the turn that completes it.

    A failed recap must not fail the turn: the learner has finished teaching and their mastery
    is already recorded, so a missing summary is a far smaller loss than a 500 that hides the
    completion from them.
    """
    existing = await db.execute(
        select(ProtegeRecap).where(ProtegeRecap.session_id == session.id)
    )
    if existing.scalars().first() is not None:
        return

    try:
        recap = await write_session_recap(
            topic_name=topic.name,
            transcript=merged["transcript"],
            misconceptions=misconceptions,
            resolved_ids=merged["resolved_misconceptions"],
            conceded_ids=merged.get("conceded_misconceptions") or [],
        )
    except Exception:
        log.exception("recap generation failed for session %s", session.id)
        return

    db.add(
        ProtegeRecap(
            id=str(uuid.uuid4()),
            session_id=session.id,
            learner_id=session.learner_id,
            topic_id=session.topic_id,
            summary=recap["summary"],
            taught_well=recap["taught_well"],
            still_shaky=recap["still_shaky"],
            understanding_score=merged["understanding_score"],
            turn_count=sum(1 for t in merged["transcript"] if t["role"] == "learner"),
        )
    )


async def _publish(session_id: str, node: str, update: dict):
    r = redis.from_url(settings.redis_url)
    try:
        await r.publish(channel_name(session_id), json.dumps({"node": node, "update": update}, default=str))
    finally:
        await r.aclose()


@router.post("/start", response_model=ProtegeTurnResult)
async def start_protege_session(req: ProtegeStartRequest, db: AsyncSession = Depends(get_db)):
    """Kicks off a Protégé Mode session: the persona asks its first naive question, seeded
    from the topic's real common misconceptions, before the learner has said anything
    (Section 9.1).
    """
    topic = await _resolve_topic(db, req.topic_name)
    misconceptions = topic.common_misconceptions
    checklist = {m["id"]: False for m in misconceptions}

    state = {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "misconceptions": misconceptions,
        "checklist": checklist,
        "transcript": [],
        "learner_turn": None,
        "understanding_score": 0.0,
        "resolved_misconceptions": [],
        "conceded_misconceptions": [],
        "persona_message": "",
        "status": "active",
        "gave_up_on": None,
    }
    result = await protege_persona_node(state)

    session = ProtegeSession(
        id=str(uuid.uuid4()),
        topic_id=topic.id,
        learner_id=req.learner_id,
        transcript_json=result["transcript"],
        understanding_score=0.0,
        misconceptions_resolved=[],
        status="active",
    )
    db.add(session)
    await db.commit()

    await _publish(session.id, "protege_persona", {"persona_message": result["persona_message"]})

    return ProtegeTurnResult(
        session_id=session.id,
        topic_name=topic.name,
        persona_message=result["persona_message"],
        understanding_score=0.0,
        checklist=_checklist_items(misconceptions, checklist),
        resolved_misconceptions=[],
        status="active",
    )


@router.post("/turn", response_model=ProtegeTurnResult)
async def submit_protege_turn(req: ProtegeTurnRequest, db: AsyncSession = Depends(get_db)):
    """Scores the learner's explanation against the open checklist, then streams the
    persona's next question — same {"node", "update"} WebSocket event shape as the main
    learning pipeline, over the same per-session Redis channel (Section 9.2, 10).
    """
    session = await db.get(ProtegeSession, req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail=f"session is {session.status}, not active")

    topic = await db.get(Topic, session.topic_id)
    misconceptions = topic.common_misconceptions
    # A misconception is closed if the learner taught it OR the persona conceded it; only the
    # first kind scores, so the two lists have to be loaded separately rather than merged.
    conceded_rows = await db.execute(
        select(ProtegeConcession.misconception_id).where(ProtegeConcession.session_id == session.id)
    )
    conceded = list(conceded_rows.scalars().all())
    closed = set(session.misconceptions_resolved) | set(conceded)
    checklist = {m["id"]: m["id"] in closed for m in misconceptions}

    state = {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "misconceptions": misconceptions,
        "checklist": checklist,
        "transcript": session.transcript_json,
        "learner_turn": req.learner_explanation,
        "understanding_score": session.understanding_score,
        "resolved_misconceptions": list(session.misconceptions_resolved),
        "conceded_misconceptions": conceded,
        "persona_message": "",
        "status": "active",
        "gave_up_on": None,
    }

    merged: dict = {}
    # The persona's own update is held back rather than published as it arrives: the pedagogy
    # guard runs after it and may rewrite the message, and a subscriber that already received
    # the pre-guard version has seen exactly what the guard exists to withhold.
    persona_update: dict | None = None
    async for step in protege_graph.astream(state):
        for node_name, update in step.items():
            merged.update(update)
            if node_name == "protege_persona":
                persona_update = update
            else:
                await _publish(session.id, node_name, update)

    if persona_update is not None:
        await _publish(
            session.id,
            "protege_persona",
            {**persona_update, "persona_message": merged["persona_message"]},
        )

    session.transcript_json = merged["transcript"]
    session.understanding_score = merged["understanding_score"]
    session.misconceptions_resolved = merged["resolved_misconceptions"]

    newly_conceded = set(merged.get("conceded_misconceptions") or []) - set(conceded)
    for mid in newly_conceded:
        db.add(ProtegeConcession(id=str(uuid.uuid4()), session_id=session.id, misconception_id=mid))

    if merged["understanding_score"] >= UNDERSTANDING_THRESHOLD or merged["status"] == "completed":
        session.status = "completed"
        await db.flush()
        # Mastery moves only on what the learner actually taught. A session that ran out of
        # open misconceptions because the persona conceded them is finished, not passed, and
        # folding it into mastery would reward saying "I don't know" until nothing is left.
        if merged["understanding_score"] >= UNDERSTANDING_THRESHOLD:
            await recompute_mastery(db, session.learner_id, session.topic_id)
        await _write_recap(db, session, topic, misconceptions, merged)
    await db.commit()

    return ProtegeTurnResult(
        session_id=session.id,
        topic_name=topic.name,
        persona_message=merged["persona_message"],
        understanding_score=merged["understanding_score"],
        checklist=_checklist_items(misconceptions, merged["checklist"]),
        resolved_misconceptions=merged["resolved_misconceptions"],
        status=session.status,
    )


async def _recap_result(db, recap: ProtegeRecap) -> ProtegeRecapResult:
    topic = await db.get(Topic, recap.topic_id)
    return ProtegeRecapResult(
        session_id=recap.session_id,
        topic_id=recap.topic_id,
        topic_name=topic.name if topic else recap.topic_id,
        summary=recap.summary,
        taught_well=recap.taught_well,
        still_shaky=recap.still_shaky,
        understanding_score=recap.understanding_score,
        turn_count=recap.turn_count,
        created_at=recap.created_at,
    )


@router.get("/recaps", response_model=list[ProtegeRecapResult])
async def list_protege_recaps(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Every finished teach-back for one learner, newest first."""
    result = await db.execute(
        select(ProtegeRecap)
        .where(ProtegeRecap.learner_id == learner_id)
        .order_by(ProtegeRecap.created_at.desc())
    )
    return [await _recap_result(db, r) for r in result.scalars().all()]


@router.get("/{session_id}/recap", response_model=ProtegeRecapResult)
async def get_protege_recap(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProtegeRecap).where(ProtegeRecap.session_id == session_id))
    recap = result.scalars().first()
    if recap is None:
        raise HTTPException(status_code=404, detail="no recap — session hasn't completed yet")
    return await _recap_result(db, recap)


@router.post("/publish")
async def publish_protege_explanation(req: ProtegePublishRequest, db: AsyncSession = Depends(get_db)):
    """On publish, the transcript is screened by the same Moderation Service as any other
    Q&A post, then lands in the topic-scoped feed tagged as a Protégé-Mode explanation so
    other learners can see how a peer taught their way through the same misconceptions
    (Section 9.4, 7.2).
    """
    session = await db.get(ProtegeSession, req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="session hasn't cleared the understanding threshold yet")

    body = "\n\n".join(
        f"{'Me' if turn['role'] == 'learner' else 'Confused peer'}: {turn['content']}"
        for turn in session.transcript_json
    )
    status = moderate_text(body)
    post = QnaPost(
        id=str(uuid.uuid4()),
        topic_id=session.topic_id,
        author_id=session.learner_id,
        body=body,
        moderation_status=status,
        source="protege_explanation",
    )
    db.add(post)
    session.status = "published"
    await db.commit()

    return {"id": post.id, "moderation_status": status}
