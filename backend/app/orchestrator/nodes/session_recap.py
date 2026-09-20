"""Session Recap — turns a finished Protégé transcript into something worth re-reading.

Called once, when a session clears the understanding threshold. Not a graph node: it runs
after the per-turn graph has finished and the session is already complete, so it takes the
stored session rather than participating in a turn.

The recap is written in second person and about the *teaching*, not the topic — a summary of
limits would duplicate the lesson the learner already has. What they can't reconstruct later
is which of their own explanations actually landed, and which one the persona kept circling
back to. That's the artifact.

Follows the same convention as the LLM-backed nodes: a tool schema, one forced_tool_call, and
a deterministic stub with the identical shape when there's no key or the call fails.
"""

from app.llm import forced_tool_call

_RECAP_TOOL = {
    "name": "write_recap",
    "description": "Summarize a finished teach-back session for the learner who taught it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "3-5 sentences, second person, about how they taught — which explanations "
                    "worked, where the persona stayed confused, how they recovered. Not a "
                    "summary of the subject matter."
                ),
            },
            "taught_well": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string"},
                "description": "Short phrases naming explanations that visibly resolved a confusion.",
            },
            "still_shaky": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string"},
                "description": "Short phrases naming points they got through but explained thinly.",
            },
        },
        "required": ["summary", "taught_well", "still_shaky"],
    },
}


def _stub_recap(topic_name: str, resolved: list[dict], unresolved: list[dict], turns: int) -> dict:
    covered = ", ".join(m["sub_concept"] for m in resolved) or "nothing yet"
    return {
        "summary": (
            f"You taught {topic_name} across {turns} turns and resolved "
            f"{len(resolved)} of {len(resolved) + len(unresolved)} misconceptions. Covered: {covered}."
        ),
        "taught_well": [m["sub_concept"] for m in resolved][:4],
        "still_shaky": [m["sub_concept"] for m in unresolved][:4],
    }


async def write_session_recap(
    topic_name: str,
    transcript: list[dict],
    misconceptions: list[dict],
    resolved_ids: list[str],
) -> dict:
    resolved = [m for m in misconceptions if m["id"] in resolved_ids]
    unresolved = [m for m in misconceptions if m["id"] not in resolved_ids]
    learner_turns = [t for t in transcript if t["role"] == "learner"]

    stub = _stub_recap(topic_name, resolved, unresolved, len(learner_turns))
    if not transcript:
        return stub

    system = (
        "You are reviewing a completed teach-back session. A learner taught a deliberately "
        "confused AI student, and cleared the bar. Write the recap FOR THE LEARNER, in second "
        "person.\n\n"
        "Judge the teaching, not the topic. Do not re-explain the subject — they already have "
        "the lesson. Point at their actual words: which explanation made the confusion go away, "
        "where they had to try twice, what they asserted without justifying. Be specific and "
        "concrete; a generic 'great job' recap is worthless."
    )
    convo = "\n".join(
        f"{'LEARNER' if t['role'] == 'learner' else 'CONFUSED STUDENT'}: {t['content']}"
        for t in transcript
    )
    resolved_names = ", ".join(m["sub_concept"] for m in resolved) or "none"
    unresolved_names = ", ".join(m["sub_concept"] for m in unresolved) or "none"
    content = (
        f"Topic: {topic_name}\n"
        f"Misconceptions they resolved: {resolved_names}\n"
        f"Still open at the end: {unresolved_names}\n\n"
        f"Full transcript:\n{convo}"
    )

    result = await forced_tool_call(system, content, _RECAP_TOOL, max_tokens=600)
    if result is None:
        return stub
    return {
        "summary": result.get("summary") or stub["summary"],
        "taught_well": result.get("taught_well") or stub["taught_well"],
        "still_shaky": result.get("still_shaky") or stub["still_shaky"],
    }
