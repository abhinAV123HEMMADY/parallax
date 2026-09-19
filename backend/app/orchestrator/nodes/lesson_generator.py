"""Lesson Generator Agent — produces a structured lesson: overview, worked examples,
common mistakes (Section 4.4).

Live path: a Claude call constrained to the lesson JSON shape via forced tool use, so the
frontend renders each section without any parsing. When the session came from a snapped
photo, the localized error is passed as context so the lesson attacks the learner's actual
mistake rather than teaching the topic generically. Stub fallback keeps the same shape.
"""

from app.llm import forced_tool_call
from app.orchestrator.state import LearningState

_LESSON_TOOL = {
    "name": "write_lesson",
    "description": "Write the structured lesson.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic_name": {"type": "string"},
            "overview": {
                "type": "string",
                "description": "2-4 sentences: what the concept is and why it matters, concrete not vague.",
            },
            "worked_examples": {
                "type": "array",
                "minItems": 2,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                        "prompt": {"type": "string"},
                        "solution": {"type": "string", "description": "Numbered step-by-step solution."},
                    },
                    "required": ["difficulty", "prompt", "solution"],
                },
            },
            "common_mistakes": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
        },
        "required": ["topic_name", "overview", "worked_examples", "common_mistakes"],
    },
}

_SYSTEM = (
    "You are a tutor writing a tight, concrete micro-lesson for one learner. No filler, no "
    "'in this lesson we will' framing — teach directly. Worked examples must be fully solved "
    "with real numbers/specifics, steps separated by newlines. Common mistakes must be "
    "mistakes learners actually make on this topic, stated specifically."
)


def _stub_lesson(topic_name: str) -> dict:
    return {
        "topic_name": topic_name,
        "overview": f"{topic_name} builds on a small set of core ideas. This lesson walks "
        f"through the definition, a worked example, and the mistakes learners most often make.",
        "worked_examples": [
            {
                "difficulty": "easy",
                "prompt": f"A basic {topic_name} example.",
                "solution": "Step-by-step solution would go here.",
            },
            {
                "difficulty": "medium",
                "prompt": f"A more involved {topic_name} example.",
                "solution": "Step-by-step solution would go here.",
            },
        ],
        "common_mistakes": [
            f"Forgetting a key step specific to {topic_name}.",
            "Applying the right method to the wrong part of the problem.",
        ],
    }


async def lesson_generator_node(state: LearningState) -> dict:
    objectives = state["parsed_objectives"]
    topic_name = objectives["topic_name"]

    prompt = (
        f"Topic: {topic_name} (subject: {objectives.get('subject', 'general')})\n"
        f"Learning objectives:\n" + "\n".join(f"- {o}" for o in objectives.get("objectives", []))
    )
    if objectives.get("blocked_on_gap"):
        prompt += (
            f"\n\nContext: the learner actually asked about '{objectives['blocked_on_gap']}', "
            f"but their mastery of the prerequisite '{topic_name}' is below threshold, so this "
            "lesson targets the prerequisite. Where natural, connect it forward to what it unlocks."
        )
    error = state.get("error_analysis")
    if error and error.get("first_error_step", -1) >= 0:
        wrong = error["steps"][error["first_error_step"]]
        prompt += (
            f"\n\nContext: this session started from a photo of the learner's own work on "
            f"'{error.get('problem_statement', 'a problem')}'. Their first wrong step was: "
            f"\"{wrong['text']}\" — {error.get('error_explanation', '')} Address this exact "
            "mistake in the lesson and include it among the common mistakes."
        )

    lesson = await forced_tool_call(_SYSTEM, prompt, _LESSON_TOOL)
    if lesson is None:
        lesson = _stub_lesson(topic_name)
    lesson.setdefault("topic_name", topic_name)
    return {"lesson": lesson}
