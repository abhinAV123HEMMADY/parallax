"""Turns a learner's video notes on a topic into FSRS-scheduled flashcards.

This is what keeps notes from being a separate notebook bolted onto the side: a moment the
learner stopped a lecture to mark becomes a card that comes back on a schedule. The notes are
already the highest-signal content the learner has produced about that topic — they chose those
moments.

Card *content* is generated; card *scheduling* is the existing real FSRS initialisation, matching
flashcard_fsrs.py. Stub fallback turns each note into a cloze-style prompt from its own text, so
the feature works with no key.
"""

from datetime import datetime, timedelta

from app.fsrs.scheduler import DEFAULT_DIFFICULTY, next_interval
from app.llm import forced_tool_call

# Matches flashcard_fsrs.py. A new card starts at stability 2.0 rather than the model's 1.0
# default so its first review lands a few days out instead of immediately.
INITIAL_STABILITY = 2.0

MAX_CARDS = 12

_CARDS_TOOL = {
    "name": "write_cards",
    "description": "Write flashcards from the learner's own notes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_CARDS,
                "items": {
                    "type": "object",
                    "properties": {
                        "front": {
                            "type": "string",
                            "description": "A question testing recall of one idea. Never references 'the note'.",
                        },
                        "back": {
                            "type": "string",
                            "description": "The answer, self-contained, 1-3 sentences.",
                        },
                    },
                    "required": ["front", "back"],
                },
            }
        },
        "required": ["cards"],
    },
}

_SYSTEM = (
    "You write spaced-repetition flashcards from a learner's own notes on a lecture. Each card "
    "tests exactly one idea and must stand alone — the learner will see it weeks later with no "
    "context, so never write 'as mentioned in the note' or refer to a timestamp. Prefer the "
    "learner's own phrasing where it is already clear. Write fewer, better cards rather than "
    "padding to the maximum."
)


def _stub_cards(notes: list[dict]) -> list[dict]:
    """One card per note, built from the note's own text.

    Deliberately literal: without a model there's no way to turn a note into a good question, so
    it asks what the learner recorded at that moment rather than inventing a question the note
    may not answer.
    """
    cards = []
    for note in notes[:MAX_CARDS]:
        text = (note.get("learner_text") or "").strip()
        if not text:
            continue
        minutes, seconds = divmod(int(note.get("t_seconds", 0)), 60)
        back = text
        excerpt = (note.get("transcript_excerpt") or "").strip()
        if excerpt:
            back = f"{text}\n\nFrom the lecture: {excerpt[:200]}"
        cards.append(
            {
                "front": f"In \u201c{note.get('video_title', 'the lecture')}\u201d at {minutes}:{seconds:02d}, "
                "what did you mark as worth remembering?",
                "back": back,
            }
        )
    return cards


def _initial_card(front: str, back: str) -> dict:
    due_in_days = next_interval(INITIAL_STABILITY)
    return {
        "front": front.strip(),
        "back": back.strip(),
        "stability": INITIAL_STABILITY,
        "difficulty": DEFAULT_DIFFICULTY,
        "elapsed_days": 0,
        "due_date": datetime.utcnow() + timedelta(days=due_in_days),
    }


async def cards_from_notes(topic_name: str, notes: list[dict]) -> list[dict]:
    """Returns FSRS-initialised card dicts ready to persist. Never raises on model failure."""
    if not notes:
        return []

    rendered = "\n\n".join(
        f"Note at {n.get('t_seconds', 0)}s in \u201c{n.get('video_title', '')}\u201d:\n"
        f"  Learner wrote: {n.get('learner_text', '')}\n"
        f"  Lecture said: {n.get('transcript_excerpt') or '(no transcript)'}"
        for n in notes
    )
    prompt = (
        f"Topic: {topic_name}\n"
        f"The learner marked {len(notes)} moments while watching. Write flashcards from them.\n\n"
        f"{rendered}"
    )

    result = await forced_tool_call(_SYSTEM, prompt, _CARDS_TOOL, max_tokens=1500)
    raw = (result or {}).get("cards") if result else None
    if not raw:
        raw = _stub_cards(notes)

    cards = [
        _initial_card(c["front"], c["back"])
        for c in raw
        if isinstance(c, dict) and c.get("front") and c.get("back")
    ]
    return cards[:MAX_CARDS]
