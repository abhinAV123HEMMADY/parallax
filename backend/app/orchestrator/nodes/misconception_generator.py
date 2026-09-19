"""Generates a topic's common-misconception set for Protégé Mode on first use (Section 9.1).

Real implementation: a Claude call via the shared forced-tool-use helper. Falls back to a
generic-but-topic-flavored template when no ANTHROPIC_API_KEY is configured, so a learner can
start Protégé Mode on any topic — not just the ones seeded with a hand-written set — without
requiring a live key. Whichever path runs, the result is cached on the topic's
common_misconceptions column so it's generated once per topic, not once per session.
"""

from app.llm import forced_tool_call

_MISCONCEPTIONS_TOOL = {
    "name": "generate_misconceptions",
    "description": "Produce realistic common misconceptions a confused student would hold about this topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "misconceptions": {
                "type": "array",
                "minItems": 4,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "short kebab-case id"},
                        "sub_concept": {
                            "type": "string",
                            "description": "the correct sub-concept this misconception gets wrong",
                        },
                        "misconception_prompt": {
                            "type": "string",
                            "description": "one short, genuinely confused first-person question a naive student would ask",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-6 words/phrases a correct explanation would plausibly use",
                        },
                        "hint": {
                            "type": "string",
                            "description": "a nudge toward the idea without giving away the full answer",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "the correct 1-2 sentence explanation of this sub-concept",
                        },
                    },
                    "required": ["id", "sub_concept", "misconception_prompt", "keywords", "hint", "explanation"],
                },
            },
        },
        "required": ["misconceptions"],
    },
}

_SYSTEM = (
    "You write realistic common misconceptions that students hold about a given topic, for a "
    "'teach the AI' exercise: the AI will play a naive student who genuinely holds each "
    "misconception until a human tutor's explanation resolves it. Misconceptions should be "
    "specific to the topic (not generic study-skills confusion) and cover distinct "
    "sub-concepts a learner needs to actually understand."
)


_GENERIC_IDS = {"purpose", "mechanism", "common-mistake", "when-it-applies"}


def is_generic_set(misconceptions: list[dict] | None) -> bool:
    """True when a topic's cached misconceptions are the keyless fallback template — used to
    regenerate them once a live LLM becomes available."""
    if not misconceptions:
        return True
    return {m.get("id") for m in misconceptions} <= _GENERIC_IDS


def _generic_misconceptions(topic_name: str) -> list[dict]:
    return [
        {
            "id": "purpose",
            "sub_concept": f"What {topic_name} actually is and the problem it solves",
            "misconception_prompt": f"Wait, what even is {topic_name} for? Why do we need it?",
            "keywords": [topic_name.lower(), "purpose", "why", "used for", "solves"],
            "hint": f"Think about what would go wrong, or what question would be unanswerable, without {topic_name}.",
            "explanation": f"{topic_name} exists to solve a specific, nameable problem — that problem is the starting point, not the mechanics.",
        },
        {
            "id": "mechanism",
            "sub_concept": f"The core mechanism behind {topic_name}, step by step",
            "misconception_prompt": f"Okay but how does {topic_name} actually work, step by step?",
            "keywords": ["step", "process", "works by", "mechanism", "first", "then"],
            "hint": f"Try breaking {topic_name} into the smallest steps you can name in order.",
            "explanation": f"{topic_name} works through a specific sequence of steps — naming that sequence, in order, is the core mechanism.",
        },
        {
            "id": "common-mistake",
            "sub_concept": f"The most common mistake learners make with {topic_name}",
            "misconception_prompt": f"Is there some obvious mistake people make with {topic_name} that I should watch out for?",
            "keywords": ["mistake", "confuse", "wrong", "careful", "instead of"],
            "hint": f"Think about what a learner would do if they applied {topic_name} too literally or too early.",
            "explanation": f"The most common mistake with {topic_name} is applying it in a case where its assumptions don't actually hold.",
        },
        {
            "id": "when-it-applies",
            "sub_concept": f"When {topic_name} applies versus when it doesn't",
            "misconception_prompt": f"How do I know when I should actually use {topic_name} instead of something else?",
            "keywords": ["applies", "when", "instead", "condition", "only works"],
            "hint": f"Think about the specific condition that has to be true before {topic_name} is even the right tool.",
            "explanation": f"{topic_name} applies only under specific conditions — recognizing those conditions is what separates using it correctly from misapplying it.",
        },
    ]


async def generate_misconceptions(topic_name: str, subject: str) -> list[dict]:
    result = await forced_tool_call(
        _SYSTEM,
        f"Topic: {topic_name}\nSubject area: {subject}\n\nGenerate 4-5 misconceptions.",
        _MISCONCEPTIONS_TOOL,
        max_tokens=1500,
    )
    if result:
        return result.get("misconceptions") or _generic_misconceptions(topic_name)
    return _generic_misconceptions(topic_name)
