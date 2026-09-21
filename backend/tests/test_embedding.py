"""Guards the embedding layer against regressing to a hash placeholder.

The point of these tests is not that some particular cosine number is right — it's that the
embeddings are *semantic at all*. The function these replaced hashed the input and returned a
random unit vector, so it passed every "returns 384 floats" check while making every pgvector
ranking in the system arbitrary. A shape assertion would not have caught that; an ordering
assertion does.
"""

import pytest
from parallax_embed import EMBEDDING_DIM, embed_document, embed_documents, embed_query

# Straight from backend/scripts/seed.py — if these stop matching the seeded corpus, transcript
# search is being tested against inputs it never sees in practice.
TOPIC = "limits"
MATCHING_VIDEO_TITLE = "Introduction to limits | Khan Academy"
UNRELATED_TOPIC = "chain rule"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b)


def test_dimension_matches_schema():
    """384 is not arbitrary: it's EMBEDDING_DIM in app/models/topic.py and the width of every
    Vector column. A model with a different width needs a migration, not just a config change.
    """
    assert len(embed_document("derivatives")) == EMBEDDING_DIM


def test_vectors_are_unit_length():
    """pgvector's cosine operator doesn't require normalized input, but the seeded corpus was
    unit-length under the old function and the exam/mastery code compares scores across rows
    seeded at different times. Keeping the invariant avoids mixing scales."""
    assert cosine(embed_document("integration by parts"), embed_document("integration by parts")) == pytest.approx(1.0, abs=1e-5)


def test_related_text_scores_above_unrelated():
    """The regression that matters. Under the old hash embedding this assertion failed: the
    topic scored -0.043 against its own matching video title and -0.021 against an unrelated
    topic, i.e. ranking was noise.
    """
    topic = embed_document(TOPIC)
    match = cosine(topic, embed_document(MATCHING_VIDEO_TITLE))
    unrelated = cosine(topic, embed_document(UNRELATED_TOPIC))

    assert match > unrelated, f"matching title {match:.4f} did not beat unrelated {unrelated:.4f}"
    # A real model clears this comfortably (~0.81 vs ~0.66 when written). The threshold is
    # deliberately far below that so a model swap doesn't fail the suite, while a regression to
    # hash embeddings (which scores near zero, often negative) still does.
    assert match > 0.5


def test_morphological_variants_are_close():
    """'derivative' and 'derivatives' must land near each other — learners type both, and the
    topic-suggestion path depends on that tolerance."""
    assert cosine(embed_document("derivatives"), embed_document("derivative")) > 0.8


def test_batch_matches_single():
    """embed_documents is used for seeding and caption ingest; embed_document for one-offs.
    They must agree, or the same text embeds differently depending on the write path."""
    texts = ["limits", "derivatives"]
    batched = embed_documents(texts)
    assert len(batched) == 2
    for text, vector in zip(texts, batched):
        assert cosine(vector, embed_document(text)) == pytest.approx(1.0, abs=1e-5)


def test_empty_batch_returns_empty():
    """Caption ingest can legitimately receive a video with no cues; that must not reach the model."""
    assert embed_documents([]) == []


def test_query_embedding_still_matches_its_document():
    """embed_query applies bge's instruction prefix and embed_document doesn't — that asymmetry
    is intentional, but it must not push a query away from the passage it should retrieve."""
    query = embed_query(TOPIC)
    assert cosine(query, embed_document(MATCHING_VIDEO_TITLE)) > cosine(
        query, embed_document(UNRELATED_TOPIC)
    )
