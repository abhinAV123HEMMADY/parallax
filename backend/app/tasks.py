import asyncio
import json

import redis.asyncio as redis

from app.celery_app import celery_app
from app.config import settings
from app.orchestrator.graph import learning_graph
from app.realtime import channel_name


async def _run_pipeline(session_id: str, learner_id: str, topic_input: str, input_mode: str):
    r = redis.from_url(settings.redis_url)
    initial_state = {
        "topic_input": topic_input,
        "input_mode": input_mode,
        "learner_id": learner_id,
        "session_id": session_id,
        "parsed_objectives": {},
        "prerequisite_gap": None,
        "error_analysis": None,
        "lesson": {},
        "quiz": [],
        "flashcards": [],
        "confidence_ratings": {},
        "videos": [],
        "tutor_matches": [],
    }

    try:
        # astream yields {node_name: partial_state_update} after every node completes —
        # this is what lets the lesson render while the quiz/flashcards/videos are still
        # generating in parallel branches (Section 10).
        async for step in learning_graph.astream(initial_state):
            for node_name, update in step.items():
                await r.publish(
                    channel_name(session_id),
                    json.dumps({"node": node_name, "update": update}, default=str),
                )
        await r.publish(channel_name(session_id), json.dumps({"node": "_done", "update": {}}))
    finally:
        await r.aclose()


@celery_app.task(name="run_learning_pipeline")
def run_learning_pipeline(session_id: str, learner_id: str, topic_input: str, input_mode: str):
    asyncio.run(_run_pipeline(session_id, learner_id, topic_input, input_mode))
