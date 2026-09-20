"""Pedagogy Guard — the last thing that runs before a persona message reaches the learner.

The persona is *told* not to give the answer away ("offer one small concrete hint that nudges
them toward the idea without giving away the full answer" in protege_persona). That's a soft
instruction in a prompt, and models break it exactly when the learner sounds frustrated — the
same failure class video_qa already guards structurally by validating timestamps instead of
trusting them. This node is that check for answer leakage.

What counts as a leak is narrower than "mentions the concept": the message must state the
resolution of a misconception the learner has NOT yet reached. Explaining something already
on the checklist is fine, and so is a hint that points at the idea without closing it.

Two paths are deliberately exempt. When `gave_up_on` is set the persona is explaining on
purpose after two consecutive punts, which is the designed escape from an infinite loop — the
guard must not undo it. And with no open misconceptions left the message is the wrap-up line,
which has nothing to leak.
"""

from app.llm import forced_tool_call, llm_enabled
from app.orchestrator.protege_state import ProtegeState

_JUDGE_TOOL = {
    "name": "judge_message",
    "description": "Decide whether the student-persona message gives away an unreached answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "leaks": {
                "type": "boolean",
                "description": "True only if the message states the resolution of a listed open misconception.",
            },
            "reason": {"type": "string", "description": "One short sentence of justification."},
        },
        "required": ["leaks", "reason"],
    },
}

_REWRITE_TOOL = {
    "name": "rewrite_as_hint",
    "description": "Rewrite the message so it nudges without resolving.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The rewritten in-character message."},
        },
        "required": ["message"],
    },
}


async def _judge(message: str, open_misconceptions: list[dict]) -> dict | None:
    system = (
        "You audit a tutoring transcript for answer leakage. The speaker is an AI playing a "
        "confused student; the human is teaching it. The point of the exercise is that the "
        "human reaches each idea themselves.\n\n"
        "Flag the message ONLY if it states the resolution of one of the listed open "
        "misconceptions — i.e. a learner reading it no longer has to work that idea out. "
        "Do NOT flag: questions, expressions of confusion, partial hints, restatements of "
        "what the human already said, or anything about a concept not on the list."
    )
    listed = "\n".join(
        f'- {m["sub_concept"]}: resolving it means conveying "{m.get("explanation", m["misconception_prompt"])}"'
        for m in open_misconceptions
    )
    content = f"Open misconceptions:\n{listed}\n\nMessage to audit:\n{message}"
    return await forced_tool_call(system, content, _JUDGE_TOOL, max_tokens=200)


async def _rewrite(message: str, open_misconceptions: list[dict], topic_name: str) -> str | None:
    system = (
        f"You are a naive student being taught {topic_name} by a peer tutor. Your previous "
        "reply gave away an answer the tutor was supposed to lead you to. Rewrite it so it "
        "points toward the idea without stating it: stay in character as a confused student, "
        "ask exactly one short question, and do not resolve the confusion yourself. Keep any "
        "encouragement, drop the explanation."
    )
    listed = "\n".join(f'- {m["sub_concept"]}: "{m["misconception_prompt"]}"' for m in open_misconceptions)
    content = f"Your open confusions:\n{listed}\n\nYour reply that leaked:\n{message}"
    result = await forced_tool_call(system, content, _REWRITE_TOOL, max_tokens=250)
    return result["message"].strip() if result else None


def _fallback_hint(open_misconceptions: list[dict]) -> str:
    first = open_misconceptions[0]
    return f"Hmm, I'm still not quite there — {first['misconception_prompt']}"


async def pedagogy_guard_node(state: ProtegeState) -> dict:
    message = state["persona_message"]
    open_misconceptions = [m for m in state["misconceptions"] if not state["checklist"].get(m["id"])]

    if state.get("gave_up_on") or not open_misconceptions or not message or not llm_enabled():
        return {"guard_verdict": "skipped"}

    verdict = await _judge(message, open_misconceptions)
    if verdict is None or not verdict.get("leaks"):
        return {"guard_verdict": "passed"}

    # The rewrite is judged again before it ships. The model being asked to fix the leak is the
    # one that just produced it, and it is shown the leaking text as context, so "rewrote it but
    # kept the answer in" is a realistic outcome rather than a paranoid one. The deterministic
    # hint is the floor: it cannot leak because it only ever restates an open question.
    safe = await _rewrite(message, open_misconceptions, state["topic_name"])
    if safe is not None:
        recheck = await _judge(safe, open_misconceptions)
        if recheck is not None and recheck.get("leaks"):
            safe = None
    if safe is None:
        safe = _fallback_hint(open_misconceptions)

    # The persona already appended its message to the transcript, so replacing only
    # persona_message would leave the leaked wording in the session history that the next
    # turn's prompt is built from.
    transcript = list(state["transcript"])
    if transcript and transcript[-1]["role"] == "persona":
        transcript[-1] = {"role": "persona", "content": safe}

    return {"persona_message": safe, "transcript": transcript, "guard_verdict": "blocked"}
