"""Snap-a-Problem Agent — error-step localization on photographed work.

Given a photo of a student's (typically handwritten) attempt, this node does more than name
the topic: it transcribes the solution steps, finds the FIRST step where the reasoning
breaks, and names the *prerequisite concept* that mistake reveals a gap in — which is then
written into the mastery graph as a real gap (score capped low + a struggle event), so a
single photo visibly flips a node on the Mastery Map and redirects the rest of the pipeline
at the true upstream weakness.

Live path: a Claude vision call constrained to structured output. Stub path (no key, or the
input isn't an actual image payload): a canned integration-by-parts analysis with the same
shape, so the whole flow — including the mastery-graph flip — demos without a key.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import async_session
from app.llm import forced_tool_call
from app.models import MasteryScore, StruggleEvent, Topic
from app.orchestrator.state import LearningState

GAP_SCORE_CAP = 0.35  # a localized error caps the prerequisite's mastery below gap threshold

_LOCALIZE_TOOL = {
    "name": "localize_error",
    "description": "Report the transcribed solution steps and the first incorrect one.",
    "input_schema": {
        "type": "object",
        "properties": {
            "problem_statement": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The step, transcribed."},
                        "correct": {"type": "boolean"},
                        "note": {"type": "string", "description": "Only for the wrong step: what went wrong."},
                    },
                    "required": ["text", "correct"],
                },
            },
            "first_error_step": {
                "type": "integer",
                "description": "0-based index of the first incorrect step, or -1 if the work is correct.",
            },
            "error_explanation": {"type": "string"},
            "tested_concept": {
                "type": "string",
                "description": "Lowercase common name of the concept the problem tests, e.g. 'integration by parts'.",
            },
            "prerequisite_concept": {
                "type": "string",
                "description": "Lowercase name of the single prerequisite concept the error reveals a gap in.",
            },
        },
        "required": [
            "problem_statement", "steps", "first_error_step",
            "error_explanation", "tested_concept", "prerequisite_concept",
        ],
    },
}

_SYSTEM = (
    "You are analyzing a photo of a student's worked attempt at a problem. Transcribe their "
    "solution as discrete steps exactly as written (do not fix anything). Find the FIRST step "
    "where the reasoning or computation breaks. Then make the diagnostic leap: name the "
    "concept the problem is testing, and the single upstream prerequisite concept this "
    "specific mistake reveals the student is shaky on — the concept a tutor would reteach "
    "first. If the work is fully correct, set first_error_step to -1."
)


def _stub_analysis() -> dict:
    """Canned analysis of a classic integration-by-parts slip whose real cause is a
    differentiation error — the prerequisite gap is 'derivatives', not the topic itself."""
    return {
        "problem_statement": "∫ x·cos(x) dx",
        "steps": [
            {"text": "Let u = x, dv = cos(x) dx", "correct": True},
            {"text": "du = dx, v = sin(x)", "correct": True},
            {"text": "∫ x·cos(x) dx = x·sin(x) − ∫ sin(x) dx", "correct": True},
            {
                "text": "= x·sin(x) − cos(x) + C",
                "correct": False,
                "note": "The integral of sin(x) is −cos(x); subtracting it gives +cos(x). Sign error rooted in the derivative/antiderivative pairs.",
            },
        ],
        "first_error_step": 3,
        "error_explanation": (
            "The setup of integration by parts is correct — the slip is in the final "
            "antiderivative of sin(x), which is a derivatives-level fact, not an "
            "integration-by-parts fact."
        ),
        "tested_concept": "integration by parts",
        "prerequisite_concept": "derivatives",
    }


def _image_payload(topic_input: str) -> tuple[str, str] | None:
    """Returns (media_type, base64_data) if topic_input is a data-URL image, else None."""
    if not topic_input.startswith("data:image/"):
        return None
    try:
        header, data = topic_input.split(",", 1)
        media_type = header.removeprefix("data:").split(";", 1)[0]
        return media_type, data
    except ValueError:
        return None


async def _flag_prerequisite_gap(learner_id: str, prerequisite_concept: str) -> str | None:
    """Write the diagnosis into the mastery graph: cap the prerequisite topic's score below
    the gap threshold and record a struggle event. Returns the topic id if one matched."""
    async with async_session() as db:
        result = await db.execute(
            select(Topic).where(Topic.name.ilike(f"%{prerequisite_concept}%"))
        )
        topic = result.scalars().first()
        if topic is None:
            return None

        existing = (
            await db.execute(
                select(MasteryScore).where(
                    MasteryScore.user_id == learner_id, MasteryScore.topic_id == topic.id
                )
            )
        ).scalars().first()
        capped = min(existing.score, GAP_SCORE_CAP) if existing else GAP_SCORE_CAP

        stmt = insert(MasteryScore).values(user_id=learner_id, topic_id=topic.id, score=capped)
        stmt = stmt.on_conflict_do_update(
            index_elements=[MasteryScore.user_id, MasteryScore.topic_id], set_={"score": capped}
        )
        await db.execute(stmt)
        db.add(
            StruggleEvent(
                id=str(uuid.uuid4()),
                user_id=learner_id,
                topic_id=topic.id,
                signal_type="prerequisite_gap",
                severity=0.8,
                visibility="private",
            )
        )
        await db.commit()
        return topic.id


async def snap_a_problem_node(state: LearningState) -> dict:
    analysis = None

    image = _image_payload(state["topic_input"])
    if image is not None:
        media_type, data = image
        analysis = await forced_tool_call(
            _SYSTEM,
            [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                },
                {"type": "text", "text": "Analyze this student's work."},
            ],
            _LOCALIZE_TOOL,
        )

    real_diagnosis = analysis is not None  # only a live vision pass over actual work counts
    if analysis is None:
        analysis = _stub_analysis()

    # The stub analysis is display-only demo content — writing mastery/struggle rows from it
    # would fabricate learner state. Only a genuine diagnosis of the learner's own snapped
    # work is allowed to touch the mastery graph.
    prerequisite_topic_id = None
    if real_diagnosis and analysis.get("first_error_step", -1) >= 0 and analysis.get("prerequisite_concept"):
        prerequisite_topic_id = await _flag_prerequisite_gap(
            state["learner_id"], analysis["prerequisite_concept"]
        )
    analysis["prerequisite_topic_id"] = prerequisite_topic_id

    return {
        "topic_input": analysis.get("tested_concept") or state["topic_input"],
        "error_analysis": analysis,
    }
