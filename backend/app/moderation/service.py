"""Screens peer feed, Q&A, and squad chat before other learners can see it (Section 2.1, 7.2).

STUB: real implementation is a Claude classification pass plus a human review queue for
anything the classifier flags (Section 11). This stub is a deterministic keyword block-list
so the moderation_status gate is real and exercised end-to-end without an LLM dependency.
"""

_BLOCKED_TERMS = {"scam", "spam", "hate"}


def moderate_text(body: str) -> str:
    lowered = body.lower()
    if any(term in lowered for term in _BLOCKED_TERMS):
        return "rejected"
    return "approved"
