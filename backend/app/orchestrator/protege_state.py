from typing import TypedDict


class ProtegeState(TypedDict):
    topic_id: str
    topic_name: str
    misconceptions: list[dict]  # [{id, sub_concept, misconception_prompt, keywords}]
    checklist: dict[str, bool]  # misconception id -> covered
    transcript: list[dict]  # [{role: "persona"|"learner", content}]
    learner_turn: str | None
    understanding_score: float
    resolved_misconceptions: list[str]
    persona_message: str
    status: str  # active|completed
    gave_up_on: str | None  # misconception id the persona just explained itself, if any, this turn
