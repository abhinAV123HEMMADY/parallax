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
    conceded_ids: list[str] | None = None,
) -> dict:
    conceded_ids = conceded_ids or []
    resolved = [m for m in misconceptions if m["id"] in resolved_ids]
    # Conceded points are ones the persona explained itself. They belong in "still shaky"
    # rather than being silently dropped — the learner never taught them, and a recap that
    # omits them reads as if the session covered less than it did.
    unresolved = [m for m in misconceptions if m["id"] not in resolved_ids]
    conceded = [m for m in misconceptions if m["id"] in conceded_ids]
    learner_turns = [t for t in transcript if t["role"] == "learner"]

    stub = _stub_recap(topic_name, resolved, unresolved, len(learner_turns))
    if not transcript:
        return stub

    system = (
        "You are reviewing a finished teach-back session. A learner taught a deliberately "
        "confused AI student. Write the recap FOR THE LEARNER, in second person.\n\n"
        "Judge the teaching, not the topic. Do not re-explain the subject — they already have "
        "the lesson. Point at their actual words: which explanation made the confusion go away, "
        "where they had to try twice, what they asserted without justifying. Be specific and "
        "concrete; a generic 'great job' recap is worthless.\n\n"
        "Some points are listed as CONCEDED: the learner said they didn't know, twice, and the "
        "student looked those up itself. Never credit the learner for a conceded point — they "
        "did not teach it. Say plainly that it went unanswered, and be honest overall: if they "
        "explained very little, the recap says so rather than inventing praise."
    )
    convo = "\n".join(
        f"{'LEARNER' if t['role'] == 'learner' else 'CONFUSED STUDENT'}: {t['content']}"
        for t in transcript
    )
    still_open = [m for m in unresolved if m["id"] not in conceded_ids]
    resolved_names = ", ".join(m["sub_concept"] for m in resolved) or "none"
    conceded_names = ", ".join(m["sub_concept"] for m in conceded) or "none"
    open_names = ", ".join(m["sub_concept"] for m in still_open) or "none"
    content = (
        f"Topic: {topic_name}\n"
        f"TAUGHT by the learner: {resolved_names}\n"
        f"CONCEDED — the learner said they didn't know and the student looked it up: {conceded_names}\n"
        f"Never reached: {open_names}\n\n"
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
