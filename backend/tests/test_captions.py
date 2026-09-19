"""Caption cue grouping — pure logic, no database and no model."""

import pytest
from app.notes.captions import (
    MAX_CUES,
    TARGET_CHUNK_SECONDS,
    CaptionTooLarge,
    Chunk,
    Cue,
    excerpt_at,
    group_cues,
    validate,
)


def cues_every(step: int, count: int) -> list[Cue]:
    return [Cue(t_seconds=i * step, text=f"sentence number {i} with enough words to matter") for i in range(count)]


def test_groups_into_target_windows():
    """One row per YouTube cue would make similarity search useless — cues are a few words each."""
    chunks = group_cues(cues_every(step=5, count=40))  # 200s of video
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert len(chunk.text) > 40, "a chunk should carry real content, not a fragment"
    starts = [c.start_seconds for c in chunks]
    assert starts == sorted(starts)
    # Windows should be near the target rather than degenerate in either direction.
    spans = [b - a for a, b in zip(starts, starts[1:])]
    assert all(span <= TARGET_CHUNK_SECONDS + 5 for span in spans)


def test_chunk_starts_at_its_first_cue():
    """Seeking to a chunk must land at the start of the passage, not inside it."""
    chunks = group_cues([Cue(t_seconds=17, text="first"), Cue(t_seconds=20, text="second")])
    assert chunks[0].start_seconds == 17


def test_out_of_order_cues_are_sorted():
    """Cues arrive from a browser extension parsing YouTube's internal format; order isn't
    guaranteed, and an unsorted chunk could start later than text it contains."""
    chunks = group_cues([Cue(t_seconds=90, text="later"), Cue(t_seconds=10, text="earlier")])
    assert chunks[0].start_seconds == 10


def test_blank_cues_dropped():
    assert group_cues([Cue(t_seconds=0, text="   "), Cue(t_seconds=1, text="")]) == []


def test_empty_input():
    assert group_cues([]) == []


def test_validate_rejects_oversized_payload():
    with pytest.raises(CaptionTooLarge):
        validate([Cue(t_seconds=i, text="x") for i in range(MAX_CUES + 1)])


def test_excerpt_picks_latest_chunk_at_or_before():
    chunks = group_cues(cues_every(step=10, count=30))
    starts = [c.start_seconds for c in chunks]
    target = starts[1]
    assert excerpt_at(chunks, target) == chunks[1].text, "exact boundary belongs to that chunk"
    assert excerpt_at(chunks, target + 3) == chunks[1].text


def test_excerpt_before_first_chunk_falls_back_to_first():
    """A learner noting something in the opening seconds, before any caption — an excerpt slightly
    after the mark beats none, which would look like a broken composer."""
    chunks = [Chunk(start_seconds=30, text="later text")]
    assert excerpt_at(chunks, 5) == "later text"


def test_excerpt_with_no_chunks_is_none():
    assert excerpt_at([], 42) is None
