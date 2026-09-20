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

# Long enough to be a sentence someone meant to send. Below this the turn is a stray keystroke
# or a half-finished thought, not an explanation and not an admission of being stuck.
_MIN_EXPLANATION_CHARS = 12


def _is_stuck(text: str) -> bool:
    """A deliberate punt ("I don't know") — score it as resolving nothing rather than risking a
    keyword false-positive on a guess, and skip the Claude call entirely.

    Deliberately phrase-only. Treating any short string as a punt made a stray "s" indis-
    tinguishable from "I give up", which sent the persona down the scripted hint branch and
    answered a question the learner had not actually declined to answer.
    """
    lowered = text.strip().lower()
    return any(phrase in lowered for phrase in _STUCK_PHRASES)


def _is_unusable(text: str) -> bool:
    """Too short to be an explanation, and not a punt — a typo, a stray key, an early send.

    Distinct from stuck on purpose: being stuck earns a hint, whereas this earns "say more".
    Hinting here would resolve a misconception the learner never got a real turn at.
    """
    lowered = text.strip().lower()
    return not _is_stuck(lowered) and len(lowered) < _MIN_EXPLANATION_CHARS


def _consecutive_stuck_count(transcript: list[dict]) -> int:
    """How many learner turns in a row (most recent first) have been a punt — used to stop
    hinting and just explain-and-move-on rather than looping the same question forever.

    An unusable turn neither continues nor breaks the run: it is not a punt, so it must not
    push the learner toward give-up, and it is not an explanation either, so a typo between
    two "I don't know"s should not reset the count and restart the loop.
    """
    count = 0
    for turn in reversed(transcript):
        if turn["role"] != "learner":
            continue
        if _is_stuck(turn["content"]):
            count += 1
        elif _is_unusable(turn["content"]):
            continue
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
    conceded_misconceptions = list(state.get("conceded_misconceptions") or [])
    transcript = list(state["transcript"]) + [{"role": "learner", "content": learner_turn}]

    gave_up_on = None
    newly_resolved: list[str] = []

    if _is_unusable(learner_turn):
        # Nothing to grade and nothing to hint at — the persona asks for a real explanation
        # and the same misconception stays open.
        pass
    elif _is_stuck(learner_turn):
        # First punt gets a hint (handled by the persona node); a second punt in a row on
        # the same open misconception means the conversation is stalled — explain it and
        # move on instead of repeating the same question forever.
        if _consecutive_stuck_count(transcript) >= 2:
            open_misconceptions = [m for m in misconceptions if not checklist.get(m["id"])]
            if open_misconceptions:
                # Conceded, NOT resolved. Closing it on the checklist is what lets the
                # conversation move on; counting it as taught would mean "I don't know",
                # repeated, walks the score to a pass — which is the one thing a teach-back
                # is supposed to be unable to do.
                gave_up_on = open_misconceptions[0]["id"]
                conceded_misconceptions.append(gave_up_on)
                checklist[gave_up_on] = True
    elif llm_enabled():
        newly_resolved = await _claude_score(learner_turn, misconceptions, checklist, transcript)
    else:
        newly_resolved = _stub_score(learner_turn, misconceptions, checklist)

    for mid in newly_resolved:
        if mid in checklist and not checklist[mid]:
            checklist[mid] = True
            resolved_misconceptions.append(mid)

    # Scored on what the learner actually taught, not on what has stopped being asked about.
    # The checklist closes on concession too, so scoring from it credited the persona's own
    # explanations to the learner.
    total = len(misconceptions) or 1
    understanding_score = round(len(set(resolved_misconceptions)) / total, 3)
    nothing_left_open = all(checklist.get(m["id"]) for m in misconceptions)

    return {
        "checklist": checklist,
        "resolved_misconceptions": resolved_misconceptions,
        "conceded_misconceptions": conceded_misconceptions,
        "understanding_score": understanding_score,
        "transcript": transcript,
        "status": "completed" if nothing_left_open else "active",
        "gave_up_on": gave_up_on,
    }
