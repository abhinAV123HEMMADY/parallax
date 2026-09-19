from typing import TypedDict


class LearningState(TypedDict):
    topic_input: str            # typed topic OR OCR/vision output
    input_mode: str              # "text" | "photo"
    learner_id: str
    session_id: str
    parsed_objectives: dict
    prerequisite_gap: str | None  # traced upstream concept, if any
    error_analysis: dict | None  # Snap-a-Problem error-step localization result
    lesson: dict
    quiz: list                   # [{question, answer, reexplanations{analogy,diagram[,video]}}]
    flashcards: list             # [{front, back, stability, difficulty, due_date}]
    confidence_ratings: dict     # card_id -> 0-5 self-rated confidence
    videos: list                 # [{url, start_seconds, relevance}]
    tutor_matches: list
