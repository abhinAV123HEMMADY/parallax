from datetime import datetime, timedelta

from app.fsrs.scheduler import DEFAULT_DIFFICULTY, next_interval
from app.orchestrator.state import LearningState

CARD_COUNT = 8


def _stub_cards(topic_name: str, lesson: dict) -> list[dict]:
    """STUB content generation: real implementation calls Claude to derive 8-15 cards
    from the lesson (Section 4.6). Card *scheduling* below is real FSRS, not stubbed.
    """
    cards = [
        {"front": f"Define {topic_name}.", "back": lesson["overview"][:120]},
        {"front": f"What mistake do learners commonly make with {topic_name}?", "back": lesson["common_mistakes"][0]},
    ]
    for example in lesson["worked_examples"]:
        cards.append({"front": example["prompt"], "back": example["solution"]})
    while len(cards) < CARD_COUNT:
        cards.append({"front": f"{topic_name} recall check #{len(cards)}", "back": "See lesson."})
    return cards[:CARD_COUNT]


async def flashcard_fsrs_node(state: LearningState) -> dict:
    topic_name = state["parsed_objectives"]["topic_name"]
    raw_cards = _stub_cards(topic_name, state["lesson"])

    initial_stability = 2.0
    due_in_days = next_interval(initial_stability)

    flashcards = [
        {
            "front": c["front"],
            "back": c["back"],
            "stability": initial_stability,
            "difficulty": DEFAULT_DIFFICULTY,
            "elapsed_days": 0,
            "due_date": (datetime.utcnow() + timedelta(days=due_in_days)).isoformat(),
        }
        for c in raw_cards
    ]
    return {"flashcards": flashcards}
