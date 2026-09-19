"""Quiz + Re-explanation Agent (Section 4.5).

The quiz is generated WITHOUT any answer outcomes — correctness only ever comes from the
learner actually answering and self-grading in the UI (POST /learn/quiz-answer), which is
what feeds real quiz accuracy into mastery. Each question ships with an analogy and a
diagram re-explanation so a genuine miss walks the modality-escalation ladder: analogy,
then diagram, then video. Analogies are cheapest and often enough; diagrams help spatial
learners; video is the most expensive fallback, so it's tried last.
"""

from app.llm import forced_tool_call
from app.orchestrator.state import LearningState

MODALITY_ORDER = ["analogy", "diagram", "video"]


def next_modality(modality_attempts: list[str]) -> str | None:
    """Returns the next untried re-explanation modality, or None once all three are spent."""
    for modality in MODALITY_ORDER:
        if modality not in modality_attempts:
            return modality
    return None


_QUIZ_TOOL = {
    "name": "write_quiz",
    "description": "Write the quiz, with per-question re-explanations for learners who miss it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string", "description": "The full correct answer, concise."},
                        "analogy": {
                            "type": "string",
                            "description": "Re-explains this question's concept through a concrete real-world analogy.",
                        },
                        "diagram": {
                            "type": "string",
                            "description": "Re-explains it spatially: a compact text/ASCII diagram with a one-line caption.",
                        },
                    },
                    "required": ["question", "answer", "analogy", "diagram"],
                },
            },
        },
        "required": ["questions"],
    },
}

_SYSTEM = (
    "You are writing a short comprehension quiz for a lesson the learner just read. For each "
    "question also write two alternative re-explanations of its concept, shown only if the "
    "learner misses it: one analogy-based, one diagram-based. Questions must be answerable "
    "from the lesson but not verbatim lookups. Keep everything tight and specific."
)


def _stub_quiz(topic_name: str) -> list[dict]:
    return [
        {
            "question": f"What is the defining property of {topic_name}?",
            "answer": "See lesson overview.",
            "reexplanations": {
                "analogy": f"Think of {topic_name} like [a real-world analogy would go here].",
                "diagram": f"[A diagram illustrating {topic_name} would render here].",
            },
        },
        {
            "question": f"Apply {topic_name} to a simple worked example.",
            "answer": "See worked examples.",
            "reexplanations": {
                "analogy": f"Imagine applying {topic_name} to something from daily life.",
                "diagram": f"[A worked-example diagram for {topic_name} would render here].",
            },
        },
    ]


async def quiz_reexplain_node(state: LearningState) -> dict:
    topic_name = state["parsed_objectives"]["topic_name"]
    lesson = state.get("lesson") or {}

    prompt = f"Topic: {topic_name}\n\nLesson overview:\n{lesson.get('overview', '(none)')}"
    mistakes = lesson.get("common_mistakes")
    if mistakes:
        prompt += "\n\nCommon mistakes covered:\n" + "\n".join(f"- {m}" for m in mistakes)

    generated = await forced_tool_call(_SYSTEM, prompt, _QUIZ_TOOL)
    if generated is None:
        return {"quiz": _stub_quiz(topic_name)}

    quiz = [
        {
            "question": q["question"],
            "answer": q["answer"],
            "reexplanations": {"analogy": q["analogy"], "diagram": q["diagram"]},
        }
        for q in generated["questions"]
    ]
    return {"quiz": quiz}
