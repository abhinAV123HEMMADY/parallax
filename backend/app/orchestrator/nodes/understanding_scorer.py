"""Understanding Scorer Agent — grades the learner's latest teach-back turn against the
topic's misconception checklist (Section 9.2).

Real implementation: a Claude call constrained to structured output (forced tool use) so the
score is a checklist match, not a vibe. Falls back to a deterministic keyword-match stub when
no ANTHROPIC_API_KEY is configured, so Protégé Mode demos without a live key like every other
agent node in this pipeline.
"""

from app.llm import forced_tool_call, llm_enabled
from app.orchestrator.protege_state import ProtegeState

_STUCK_PHRASES = ["i don't know", "i dont know", "idk", "not sure", "no idea", "no clue", "i give up"]


def _is_stuck(text: str) -> bool:
    """A punt ("I don't know") isn't an explanation — score it as resolving nothing rather
    than risking a keyword false-positive on a guess, and skip the Claude call entirely.
    """
    lowered = text.strip().lower()
    return len(lowered) < 4 or any(phrase in lowered for phrase in _STUCK_PHRASES)


def _consecutive_stuck_count(transcript: list[dict]) -> int:
    """How many learner turns in a row (most recent first) have been a punt — used to stop
    hinting and just explain-and-move-on rather than looping the same question forever.
    """
    count = 0
    for turn in reversed(transcript):
        if turn["role"] != "learner":
            continue
        if _is_stuck(turn["content"]):
            count += 1
        else:
            break
    return count


_SCORING_TOOL = {
    "name": "score_understanding",
    "description": "Score how well the learner's explanation resolves each open misconception.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resolved_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of misconceptions this turn's explanation actually resolves.",
            },
        },
        "required": ["resolved_ids"],
    },
}


def _stub_score(learner_turn: str, misconceptions: list[dict], checklist: dict[str, bool]) -> list[str]:
    """A misconception counts as resolved if the explanation mentions one of its keywords —
    the same shape a live Claude judgment would return (a list of resolved misconception ids).
    """
    lowered = learner_turn.lower()
    resolved = []
    for m in misconceptions:
        if checklist.get(m["id"]):
            continue
        if any(keyword.lower() in lowered for keyword in m["keywords"]):
            resolved.append(m["id"])
    return resolved


async def _claude_score(
    learner_turn: str, misconceptions: list[dict], checklist: dict[str, bool], transcript: list[dict]
) -> list[str]:
    open_misconceptions = [m for m in misconceptions if not checklist.get(m["id"])]
    system = (
        "You are grading a learner who is teaching a confused peer. Given the conversation so "
        "far and the learner's latest explanation, decide which of the peer's OPEN "
        "misconceptions that explanation actually resolves. Be strict: a misconception is only "
        "resolved if the explanation directly and correctly addresses it, not just adjacent to "
        "it. Call score_understanding with the resolved misconception ids."
    )
    convo = "\n".join(f"{t['role']}: {t['content']}" for t in transcript)
    open_list = "\n".join(f"- {m['id']}: {m['sub_concept']}" for m in open_misconceptions)
    content = (
        f"Conversation so far:\n{convo}\n\nOpen misconceptions:\n{open_list}\n\n"
        f"Learner's latest explanation:\n{learner_turn}"
    )
    result = await forced_tool_call(system, content, _SCORING_TOOL, max_tokens=300)
    return (result or {}).get("resolved_ids", [])


async def understanding_scorer_node(state: ProtegeState) -> dict:
    learner_turn = state["learner_turn"] or ""
    misconceptions = state["misconceptions"]
    checklist = dict(state["checklist"])
    resolved_misconceptions = list(state["resolved_misconceptions"])
    transcript = list(state["transcript"]) + [{"role": "learner", "content": learner_turn}]

    gave_up_on = None
    newly_resolved: list[str] = []

    if _is_stuck(learner_turn):
        # First punt gets a hint (handled by the persona node); a second punt in a row on
        # the same open misconception means the conversation is stalled — explain it and
        # move on instead of repeating the same question forever.
        if _consecutive_stuck_count(transcript) >= 2:
            open_misconceptions = [m for m in misconceptions if not checklist.get(m["id"])]
            if open_misconceptions:
                gave_up_on = open_misconceptions[0]["id"]
                newly_resolved = [gave_up_on]
    elif llm_enabled():
        newly_resolved = await _claude_score(learner_turn, misconceptions, checklist, transcript)
    else:
        newly_resolved = _stub_score(learner_turn, misconceptions, checklist)

    for mid in newly_resolved:
        if mid in checklist and not checklist[mid]:
            checklist[mid] = True
            resolved_misconceptions.append(mid)

    total = len(misconceptions) or 1
    understanding_score = round(sum(1 for v in checklist.values() if v) / total, 3)

    return {
        "checklist": checklist,
        "resolved_misconceptions": resolved_misconceptions,
        "understanding_score": understanding_score,
        "transcript": transcript,
        "status": "completed" if understanding_score >= 1.0 else "active",
        "gave_up_on": gave_up_on,
    }
