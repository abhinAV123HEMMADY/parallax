"""Intent Parser Agent — normalizes topic_input (or the Snap-a-Problem Agent's output)
into a concept + learning objectives.

Resolution order: exact-ish match against the seeded topics table first (cheap, and it keeps
the session anchored to the real prerequisite graph); otherwise a Claude call extracts the
canonical topic name, subject, and objectives from the free text, and we retry the table
match on the canonical name. Without a key, falls back to a slug-derived ad-hoc topic so the
rest of the graph always has a topic_id to work with.
"""

import re

from sqlalchemy import select

from app.database import async_session
from app.llm import forced_tool_call
from app.models import Topic
from app.orchestrator.state import LearningState

_PARSE_TOOL = {
    "name": "parse_intent",
    "description": "Extract the learning intent from the learner's free-text input.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic_name": {
                "type": "string",
                "description": "Canonical lowercase topic name, e.g. 'integration by parts'.",
            },
            "subject": {
                "type": "string",
                "description": "One-word subject area, lowercase, e.g. 'math', 'biology', 'history'.",
            },
            "objectives": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
                "description": "Three concrete learning objectives for this topic.",
            },
        },
        "required": ["topic_name", "subject", "objectives"],
    },
}

_SYSTEM = (
    "You normalize a learner's free-text request into a canonical topic. Strip filler "
    "('help me with', 'I have a test on'), resolve to the standard curricular name for the "
    "concept, and write three specific, checkable learning objectives."
)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _default_objectives(topic_name: str) -> list[str]:
    return [
        f"Understand the core definition of {topic_name}",
        f"Work through a worked example involving {topic_name}",
        f"Identify common mistakes learners make with {topic_name}",
    ]


async def _match_topic(name: str) -> Topic | None:
    async with async_session() as db:
        result = await db.execute(select(Topic).where(Topic.name.ilike(f"%{name}%")))
        return result.scalars().first()


async def _get_or_create_topic(topic_id: str, name: str, subject: str) -> None:
    """An ad-hoc topic (no match in the seeded table) still needs a real row: mastery_scores,
    lessons, and every other FK that references topics.id would otherwise fail the moment the
    pipeline tries to persist anything against it.
    """
    async with async_session() as db:
        if await db.get(Topic, topic_id) is None:
            db.add(Topic(id=topic_id, name=name, subject=subject))
            await db.commit()


async def intent_parser_node(state: LearningState) -> dict:
    raw_topic = state["topic_input"].strip()
    parsed = None

    topic = await _match_topic(raw_topic) if raw_topic and not raw_topic.startswith("data:") else None

    if topic is None:
        parsed = await forced_tool_call(
            _SYSTEM, f"Learner's input: {raw_topic}", _PARSE_TOOL, max_tokens=500
        )
        if parsed:
            topic = await _match_topic(parsed["topic_name"])

    if topic:
        topic_id, topic_name, subject = topic.id, topic.name, topic.subject
    elif parsed:
        topic_id, topic_name, subject = _slugify(parsed["topic_name"]), parsed["topic_name"], parsed["subject"]
        await _get_or_create_topic(topic_id, topic_name, subject)
    else:
        topic_id, topic_name, subject = _slugify(raw_topic), raw_topic, "general"
        await _get_or_create_topic(topic_id, topic_name, subject)

    objectives = parsed["objectives"] if parsed else _default_objectives(topic_name)

    return {
        "parsed_objectives": {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "subject": subject,
            "objectives": objectives,
        }
    }
