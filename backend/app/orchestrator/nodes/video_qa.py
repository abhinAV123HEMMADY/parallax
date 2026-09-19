"""Video Q&A — answers a question from one video's transcript, citing timestamps.

Follows the same shape as the other LLM-backed nodes: a tool schema, a system prompt, one
forced_tool_call, and a deterministic stub with the identical output shape when there's no key
or the call fails.

Not a graph node despite living here — it's called directly from routes_notes, because it
answers one question about one video rather than participating in the learning pipeline. It sits
with the other nodes so the LLM-call convention stays in one place.

The citations are the point. An answer that says "at 4:12 he defines the limit" is only useful if
4:12 is real, so every returned timestamp is checked against the chunks actually supplied and
dropped if it wasn't one of them. A model inventing a plausible timestamp is the expected
failure mode here, not an unlikely one — and in the UI a citation becomes a seek button, so an
invented one sends the learner to the wrong part of the lecture and looks like a product bug.
"""

from app.llm import forced_tool_call

_ASK_TOOL = {
    "name": "answer_from_transcript",
    "description": "Answer the learner's question using only the supplied transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "2-5 sentences answering the question directly, in plain language.",
            },
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "t_seconds": {
                            "type": "integer",
                            "description": "Must be one of the exact start times listed in the transcript.",
                        },
                        "quote": {
                            "type": "string",
                            "description": "A short phrase from that transcript segment.",
                        },
                    },
                    "required": ["t_seconds", "quote"],
                },
            },
        },
        "required": ["answer", "citations"],
    },
}

_SYSTEM = (
    "You answer a learner's question about a lecture video using only the transcript segments "
    "provided. Never use outside knowledge, and never invent a timestamp: every t_seconds you "
    "return must be copied exactly from a segment header in the transcript. If the transcript "
    "does not answer the question, say so plainly and cite the closest relevant segment. Be "
    "concrete and brief — the learner is mid-video."
)

# Words that carry no topical signal, so the stub doesn't rank a segment highly for containing
# "the" three times. Deliberately small: the stub's job is to be predictable, not clever.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "how", "what", "why",
    "when", "where", "this", "that", "it", "of", "to", "in", "on", "for", "and", "or", "i",
    "you", "we", "he", "she", "they", "can", "with", "about", "at", "be", "so", "if", "my",
}


def _keywords(text: str) -> set[str]:
    return {w.strip(".,?!;:()\"'").lower() for w in text.split()} - _STOPWORDS


def _stub_answer(question: str, video_title: str, chunks: list[dict]) -> dict:
    """Deterministic fallback: the segment with the most question-word overlap.

    Honest by construction — it returns a real timestamp from a real segment and the answer text
    says where to look rather than pretending to explain. The route reports `stubbed: true` so
    the UI can label it instead of passing keyword matching off as reasoning.
    """
    wanted = _keywords(question)
    best = max(
        chunks,
        key=lambda c: (len(wanted & _keywords(c["text"])), -c["t_seconds"]),
        default=None,
    )
    if best is None:
        return {"answer": "No transcript is available for this video yet.", "citations": [], "stubbed": True}

    minutes, seconds = divmod(int(best["t_seconds"]), 60)
    return {
        "answer": (
            f"The closest passage in “{video_title}” is at {minutes}:{seconds:02d}. "
            "No language model is configured, so this is a transcript keyword match rather than "
            "a generated explanation — jump to the timestamp to hear it in context."
        ),
        "citations": [{"t_seconds": int(best["t_seconds"]), "quote": best["text"][:180]}],
        "stubbed": True,
    }


def _validate_citations(citations, valid_starts: set[int]) -> list[dict]:
    """Keeps only citations pointing at a real segment start, de-duplicated and ordered.

    Dropping rather than clamping is deliberate: snapping an invented timestamp to the nearest
    real one would hide the failure and still send the learner somewhere arbitrary.
    """
    kept: list[dict] = []
    seen: set[int] = set()
    for citation in citations or []:
        try:
            t = int(citation["t_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        if t in valid_starts and t not in seen:
            seen.add(t)
            kept.append({"t_seconds": t, "quote": str(citation.get("quote", ""))[:300]})
    return sorted(kept, key=lambda c: c["t_seconds"])


async def answer_about_video(question: str, video_title: str, chunks: list[dict]) -> dict:
    """Returns {"answer", "citations", "stubbed"}. Never raises on a model failure."""
    if not chunks:
        return {"answer": "No transcript is available for this video yet.", "citations": [], "stubbed": True}

    transcript = "\n".join(f"[{c['t_seconds']}s] {c['text']}" for c in chunks)
    prompt = (
        f"Video: {video_title}\n\n"
        f"Transcript segments (the number in brackets is the exact t_seconds to cite):\n"
        f"{transcript}\n\n"
        f"Learner's question: {question}"
    )

    result = await forced_tool_call(_SYSTEM, prompt, _ASK_TOOL, max_tokens=800)
    if result is None:
        return _stub_answer(question, video_title, chunks)

    valid_starts = {int(c["t_seconds"]) for c in chunks}
    citations = _validate_citations(result.get("citations"), valid_starts)
    answer = str(result.get("answer", "")).strip()
    if not answer:
        return _stub_answer(question, video_title, chunks)

    # A live answer whose every citation was invented is worse than the stub: it reads
    # authoritative and gives the learner nowhere to verify it.
    if not citations:
        stub = _stub_answer(question, video_title, chunks)
        return {"answer": answer, "citations": stub["citations"], "stubbed": False}

    return {"answer": answer, "citations": citations, "stubbed": False}
