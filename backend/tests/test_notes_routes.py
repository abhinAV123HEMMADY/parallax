"""Note endpoints: round-trip, ownership guards, size cap, and caption ingest."""

from sqlalchemy import select

from app.config import settings
from app.models import Flashcard, Lesson, VideoTranscriptChunk

VIDEO = "testVideo01"


def note_body(learner_id: str, **overrides) -> dict:
    return {
        "learner_id": learner_id,
        "video_id": VIDEO,
        "video_title": "Test lecture on limits",
        "t_seconds": 42,
        "learner_text": "the epsilon-delta bit is the part I keep missing",
        **overrides,
    }


async def test_create_list_delete_round_trip(client, learner):
    created = (await client.post("/notes", json=note_body(learner.id))).json()
    assert created["t_seconds"] == 42
    assert created["has_screenshot"] is False

    listed = (await client.get("/notes", params={"learner_id": learner.id, "video_id": VIDEO})).json()
    assert [n["id"] for n in listed["notes"]] == [created["id"]]
    assert listed["video_title"] == "Test lecture on limits"

    deleted = await client.delete(f"/notes/{created['id']}", params={"learner_id": learner.id})
    assert deleted.status_code == 200

    after = (await client.get("/notes", params={"learner_id": learner.id, "video_id": VIDEO})).json()
    assert after["notes"] == []


async def test_notes_are_ordered_by_timestamp_not_creation(client, learner):
    """A timeline is only useful in playback order, and learners jump around a video."""
    for t in (120, 30, 75):
        await client.post("/notes", json=note_body(learner.id, t_seconds=t, learner_text=f"at {t}"))
    listed = (await client.get("/notes", params={"learner_id": learner.id, "video_id": VIDEO})).json()
    assert [n["t_seconds"] for n in listed["notes"]] == [30, 75, 120]


async def test_another_learners_note_is_forbidden(client, learner, db):
    from app.models import User

    created = (await client.post("/notes", json=note_body(learner.id))).json()
    intruder = User(id="u_intruder_test", name="Intruder", goals=[])
    db.add(intruder)
    await db.flush()

    assert (await client.get(f"/notes/{created['id']}", params={"learner_id": intruder.id})).status_code == 403
    assert (await client.delete(f"/notes/{created['id']}", params={"learner_id": intruder.id})).status_code == 403


async def test_missing_note_is_404(client, learner):
    assert (await client.get("/notes/nope", params={"learner_id": learner.id})).status_code == 404


async def test_unknown_learner_is_404(client):
    assert (await client.post("/notes", json=note_body("u_does_not_exist"))).status_code == 404


async def test_oversize_screenshot_is_413(client, learner):
    """The cap is what makes storing data URLs in a text column survivable."""
    oversized = "A" * (settings.max_screenshot_bytes + 10)
    response = await client.post("/notes", json=note_body(learner.id, screenshot=oversized))
    assert response.status_code == 413


async def test_screenshot_within_cap_is_kept_but_not_in_list(client, learner):
    """List responses omit images so a panel render doesn't pull megabytes; detail includes it."""
    small = "data:image/jpeg;base64," + "A" * 500
    created = (await client.post("/notes", json=note_body(learner.id, screenshot=small))).json()
    assert created["has_screenshot"] is True
    assert "screenshot" not in created

    detail = (await client.get(f"/notes/{created['id']}", params={"learner_id": learner.id})).json()
    assert detail["screenshot"] == small


async def test_transcript_ingest_then_excerpt_resolution(client, learner, db):
    """The end-to-end reason ingest exists: a note gets the words spoken at its timestamp."""
    cues = [
        {"t_seconds": 0, "text": "A limit describes what a function approaches."},
        {"t_seconds": 50, "text": "The derivative is the slope of a curve at a single point."},
        {"t_seconds": 100, "text": "One sided limits approach from only one direction."},
    ]
    result = (
        await client.post(
            f"/notes/videos/{VIDEO}/transcript",
            json={"video_title": "Test lecture on limits", "cues": cues},
        )
    ).json()
    assert result["cues_received"] == 3
    assert result["chunks_written"] >= 2

    created = (await client.post("/notes", json=note_body(learner.id, t_seconds=60))).json()
    assert created["transcript_excerpt"] is not None
    assert "derivative" in created["transcript_excerpt"]


async def test_reingest_replaces_rather_than_duplicates(client, db):
    body = {"video_title": "v", "cues": [{"t_seconds": 0, "text": "first pass of the transcript text"}]}
    first = (await client.post(f"/notes/videos/{VIDEO}/transcript", json=body)).json()
    assert first["replaced_existing"] is False

    second = (await client.post(f"/notes/videos/{VIDEO}/transcript", json=body)).json()
    assert second["replaced_existing"] is True

    count = len(
        (
            await db.execute(select(VideoTranscriptChunk).where(VideoTranscriptChunk.video_id == VIDEO))
        )
        .scalars()
        .all()
    )
    assert count == second["chunks_written"], "re-ingest must not interleave two transcripts"


async def test_ask_without_a_transcript_is_404(client):
    response = await client.post("/notes/videos/no-transcript-here/ask", json={"question": "what?"})
    assert response.status_code == 404


async def test_flashcards_create_a_synthetic_lesson(client, learner, topic_chain, db):
    """Flashcard.lesson_id is non-nullable, so note-derived cards need a parent Lesson. Routing
    them through a real one is also what keeps them visible to recompute_mastery."""
    topic = topic_chain[0]
    for t in (10, 20):
        await client.post("/notes", json=note_body(learner.id, t_seconds=t, topic_id=topic.id))

    result = (
        await client.post(f"/notes/topic/{topic.id}/flashcards", params={"learner_id": learner.id})
    ).json()
    assert result["notes_used"] == 2
    assert result["cards_created"] >= 1

    lesson = await db.get(Lesson, result["lesson_id"])
    assert lesson is not None
    assert lesson.learner_id == learner.id
    assert lesson.topic_id == topic.id
    assert lesson.content_json["source"] == "video_notes"

    cards = list(
        (await db.execute(select(Flashcard).where(Flashcard.lesson_id == lesson.id))).scalars().all()
    )
    assert len(cards) == result["cards_created"]
    # Cards must enter the real schedule, not sit at the column default of "due now".
    assert all(card.stability == 2.0 for card in cards)
    assert all(card.due_date is not None for card in cards)


async def test_flashcards_with_no_notes_is_404(client, learner, topic_chain):
    response = await client.post(
        f"/notes/topic/{topic_chain[2].id}/flashcards", params={"learner_id": learner.id}
    )
    assert response.status_code == 404
