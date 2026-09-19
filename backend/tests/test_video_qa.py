"""Video Q&A citation validation and the stub path.

The citations are the part worth testing. In the UI a citation becomes a seek button, so a
timestamp the model invented sends the learner to the wrong part of a lecture and reads as a
product bug. These assert that an invented timestamp never survives.
"""

from app.orchestrator.nodes.video_qa import _validate_citations, answer_about_video

CHUNKS = [
    {"t_seconds": 0, "text": "A limit describes what a function approaches."},
    {"t_seconds": 45, "text": "The derivative is the slope of a curve at a point."},
    {"t_seconds": 90, "text": "One sided limits approach from the left or the right."},
]
VALID = {0, 45, 90}


def test_fabricated_timestamp_is_dropped():
    kept = _validate_citations([{"t_seconds": 61, "quote": "invented"}], VALID)
    assert kept == [], "a timestamp not present in the supplied chunks must not reach the UI"


def test_real_timestamp_is_kept():
    kept = _validate_citations([{"t_seconds": 45, "quote": "the slope"}], VALID)
    assert kept == [{"t_seconds": 45, "quote": "the slope"}]


def test_not_clamped_to_nearest():
    """Snapping an invented timestamp to the closest real one would hide the failure and still
    send the learner somewhere arbitrary."""
    kept = _validate_citations([{"t_seconds": 46, "quote": "off by one"}], VALID)
    assert kept == []


def test_duplicates_removed_and_sorted():
    kept = _validate_citations(
        [
            {"t_seconds": 90, "quote": "c"},
            {"t_seconds": 0, "quote": "a"},
            {"t_seconds": 90, "quote": "dup"},
        ],
        VALID,
    )
    assert [c["t_seconds"] for c in kept] == [0, 90]


def test_malformed_citations_ignored():
    kept = _validate_citations(
        [{"quote": "no timestamp"}, {"t_seconds": "abc"}, None, {"t_seconds": 0, "quote": "ok"}],
        VALID,
    )
    assert [c["t_seconds"] for c in kept] == [0]


async def test_stub_path_has_documented_shape_without_a_key():
    """With no API key every LLM node falls back; the fallback must return the same shape."""
    result = await answer_about_video(
        question="what is the slope of a curve?", video_title="Calculus intro", chunks=CHUNKS
    )
    assert set(result) == {"answer", "citations", "stubbed"}
    assert result["stubbed"] is True
    assert result["answer"]
    # The stub must still cite a real segment, and should find the one about slope.
    assert len(result["citations"]) == 1
    assert result["citations"][0]["t_seconds"] in VALID
    assert result["citations"][0]["t_seconds"] == 45


async def test_no_transcript_is_handled():
    result = await answer_about_video(question="anything", video_title="x", chunks=[])
    assert result["citations"] == []
    assert result["stubbed"] is True
