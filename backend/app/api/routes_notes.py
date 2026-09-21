"""Video notes, caption ingest, and video-scoped Q&A — the backend behind the Chrome extension.

Two things here exist only because the client is an extension rather than a web page. Caption
ingest accepts a transcript scraped on youtube.com, where the fetch is same-origin and reliable,
instead of the backend fetching it server-side and getting IP-blocked. And notes carry a
screenshot, which page JavaScript cannot produce at all from a cross-origin iframe.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from parallax_embed import embed_documents

from app.config import settings
from app.database import get_db
from app.mastery.service import record_note_signal
from app.models import Flashcard, Lesson, Topic, User, VideoNote, VideoTranscriptChunk
from app.notes.captions import CaptionTooLarge, Chunk, Cue, excerpt_at, group_cues, validate
from app.notes.topic_match import suggest_topic
from app.orchestrator.nodes.notes_to_flashcards import cards_from_notes
from app.orchestrator.nodes.video_qa import answer_about_video
from app.schemas.notes import (
    GeneratedCards,
    NoteCreate,
    NoteDetail,
    NoteOut,
    TopicNotePack,
    TopicSuggestionResponse,
    TranscriptIngest,
    TranscriptIngestResult,
    VideoAskRequest,
    VideoAskResponse,
    VideoNotePack,
)
from app.topics.graph import depths_for

router = APIRouter(prefix="/notes", tags=["notes"])


async def _chunks_for(db: AsyncSession, video_id: str) -> list[VideoTranscriptChunk]:
    return list(
        (
            await db.execute(
                select(VideoTranscriptChunk)
                .where(VideoTranscriptChunk.video_id == video_id)
                .order_by(VideoTranscriptChunk.chunk_start_seconds)
            )
        )
        .scalars()
        .all()
    )


def _to_out(note: VideoNote, topic_name: str | None = None) -> NoteOut:
    return NoteOut(
        id=note.id,
        video_id=note.video_id,
        video_title=note.video_title,
        topic_id=note.topic_id,
        topic_name=topic_name,
        t_seconds=note.t_seconds,
        learner_text=note.learner_text,
        transcript_excerpt=note.transcript_excerpt,
        has_screenshot=note.screenshot is not None,
        created_at=note.created_at,
    )


async def _topic_names(db: AsyncSession, topic_ids: list[str]) -> dict[str, str]:
    ids = [t for t in set(topic_ids) if t]
    if not ids:
        return {}
    rows = (await db.execute(select(Topic.id, Topic.name).where(Topic.id.in_(ids)))).all()
    return {tid: name for tid, name in rows}


@router.post("", response_model=NoteOut)
async def create_note(payload: NoteCreate, db: AsyncSession = Depends(get_db)):
    """Records a note at a playback second.

    The transcript excerpt is resolved here rather than accepted from the client: the extension
    already has the caption track in hand, but trusting it would mean a note could claim the
    video said something it didn't. Resolving server-side from ingested chunks keeps the excerpt
    something the backend can stand behind.
    """
    if await db.get(User, payload.learner_id) is None:
        raise HTTPException(status_code=404, detail="learner not found")

    if payload.screenshot and len(payload.screenshot.encode()) > settings.max_screenshot_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"screenshot exceeds {settings.max_screenshot_bytes} bytes; downscale before upload",
        )

    chunks = await _chunks_for(db, payload.video_id)
    excerpt = excerpt_at(
        [Chunk(start_seconds=c.chunk_start_seconds, text=c.chunk_text) for c in chunks],
        payload.t_seconds,
    )

    topic_id = payload.topic_id
    if topic_id is not None:
        if await db.get(Topic, topic_id) is None:
            raise HTTPException(status_code=404, detail="topic not found")
    else:
        # No explicit topic: fall back to the suggestion, which returns None when it isn't
        # confident. An unmapped note is fine — it still renders and exports.
        transcript = " ".join(c.chunk_text for c in chunks)
        suggestion = await suggest_topic(
            db,
            payload.video_title,
            transcript,
            settings.note_topic_lexical_threshold,
            settings.note_topic_semantic_threshold,
        )
        topic_id = suggestion["chosen"].topic_id

    note = VideoNote(
        id=str(uuid.uuid4()),
        learner_id=payload.learner_id,
        video_id=payload.video_id,
        video_title=payload.video_title,
        topic_id=topic_id,
        t_seconds=payload.t_seconds,
        learner_text=payload.learner_text,
        transcript_excerpt=excerpt,
        screenshot=payload.screenshot,
    )
    db.add(note)
    await db.flush()

    await record_note_signal(db, payload.learner_id, topic_id, payload.share)
    await db.commit()

    names = await _topic_names(db, [topic_id]) if topic_id else {}
    return _to_out(note, names.get(topic_id) if topic_id else None)


@router.get("", response_model=VideoNotePack)
async def list_notes_for_video(
    learner_id: str = Query(...), video_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    notes = list(
        (
            await db.execute(
                select(VideoNote)
                .where(VideoNote.learner_id == learner_id, VideoNote.video_id == video_id)
                .order_by(VideoNote.t_seconds)
            )
        )
        .scalars()
        .all()
    )
    names = await _topic_names(db, [n.topic_id for n in notes if n.topic_id])
    title = notes[0].video_title if notes else ""
    return VideoNotePack(
        video_id=video_id,
        video_title=title,
        notes=[_to_out(n, names.get(n.topic_id) if n.topic_id else None) for n in notes],
    )


@router.get("/recent", response_model=list[NoteOut])
async def recent_notes(
    learner_id: str = Query(...), limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)
):
    """Newest notes across all videos — what the extension popup shows."""
    notes = list(
        (
            await db.execute(
                select(VideoNote)
                .where(VideoNote.learner_id == learner_id)
                .order_by(VideoNote.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    names = await _topic_names(db, [n.topic_id for n in notes if n.topic_id])
    return [_to_out(n, names.get(n.topic_id) if n.topic_id else None) for n in notes]


@router.get("/{note_id}", response_model=NoteDetail)
async def get_note(note_id: str, learner_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """A single note including its screenshot — fetched on demand so list responses stay small."""
    note = await db.get(VideoNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    if note.learner_id != learner_id:
        raise HTTPException(status_code=403, detail="note belongs to another learner")
    names = await _topic_names(db, [note.topic_id] if note.topic_id else [])
    base = _to_out(note, names.get(note.topic_id) if note.topic_id else None)
    return NoteDetail(**base.model_dump(), screenshot=note.screenshot)


@router.delete("/{note_id}")
async def delete_note(note_id: str, learner_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    note = await db.get(VideoNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    if note.learner_id != learner_id:
        raise HTTPException(status_code=403, detail="note belongs to another learner")
    await db.delete(note)
    await db.commit()
    return {"status": "deleted", "id": note_id}


@router.get("/topic/{topic_id}", response_model=TopicNotePack)
async def notes_for_topic(topic_id: str, learner_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Every note on a topic, grouped by video, videos ordered by prerequisite depth."""
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")

    notes = list(
        (
            await db.execute(
                select(VideoNote)
                .where(VideoNote.learner_id == learner_id, VideoNote.topic_id == topic_id)
                .order_by(VideoNote.t_seconds)
            )
        )
        .scalars()
        .all()
    )

    grouped: dict[str, list[VideoNote]] = {}
    for note in notes:
        grouped.setdefault(note.video_id, []).append(note)

    # Every note here shares one topic, so depth can't order videos against each other. It
    # orders the pack relative to other topics' packs and keeps the ordering logic in one place
    # for when a pack spans a topic cluster; within a topic, earliest-marked video leads.
    await depths_for(db, [topic_id])

    packs = [
        VideoNotePack(
            video_id=video_id,
            video_title=video_notes[0].video_title,
            notes=[_to_out(n, topic.name) for n in video_notes],
        )
        for video_id, video_notes in sorted(
            grouped.items(), key=lambda kv: min(n.created_at for n in kv[1])
        )
    ]
    return TopicNotePack(topic_id=topic.id, topic_name=topic.name, videos=packs)


@router.post("/videos/{video_id}/transcript", response_model=TranscriptIngestResult)
async def ingest_transcript(video_id: str, payload: TranscriptIngest, db: AsyncSession = Depends(get_db)):
    """Stores a caption track scraped by the extension as embedded transcript chunks.

    This is what turns the existing timestamp search from four seeded rows into something real:
    chunks land in the same table `search_transcripts` already queries, so every video a learner
    watches becomes searchable by the Video Curator node with no change to that path.

    Idempotent by replacement rather than upsert — re-ingesting a video after YouTube revises its
    captions should leave the video with exactly one current transcript, not two interleaved ones.
    """
    cues = [Cue(t_seconds=c.t_seconds, text=c.text) for c in payload.cues]
    try:
        validate(cues)
    except CaptionTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    chunks = group_cues(cues)

    existing = await _chunks_for(db, video_id)
    if existing:
        await db.execute(delete(VideoTranscriptChunk).where(VideoTranscriptChunk.video_id == video_id))

    if chunks:
        vectors = embed_documents([f"{payload.video_title} {c.text}" for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            db.add(
                VideoTranscriptChunk(
                    id=str(uuid.uuid4()),
                    video_id=video_id,
                    video_title=payload.video_title,
                    chunk_start_seconds=chunk.start_seconds,
                    chunk_text=chunk.text,
                    # The seeded rows carry hand-assigned difficulty levels. An ingested track
                    # has no such signal, and guessing one would put a fabricated value in a
                    # column other code filters on.
                    difficulty_level="unknown",
                    chunk_embedding=vector,
                )
            )

    await db.commit()
    return TranscriptIngestResult(
        video_id=video_id,
        cues_received=len(cues),
        chunks_written=len(chunks),
        replaced_existing=bool(existing),
    )


@router.get("/videos/{video_id}/topic-suggestion", response_model=TopicSuggestionResponse)
async def topic_suggestion(
    video_id: str, video_title: str = Query(""), db: AsyncSession = Depends(get_db)
):
    """Both strategies' guesses and scores, so the panel can show one and the choice stays auditable."""
    chunks = await _chunks_for(db, video_id)
    transcript = " ".join(c.chunk_text for c in chunks)
    title = video_title or (chunks[0].video_title if chunks else "")
    result = await suggest_topic(
        db,
        title,
        transcript,
        settings.note_topic_lexical_threshold,
        settings.note_topic_semantic_threshold,
    )
    return TopicSuggestionResponse(
        chosen=result["chosen"].__dict__,
        lexical=result["lexical"].__dict__,
        semantic=result["semantic"].__dict__,
    )


@router.post("/videos/{video_id}/ask", response_model=VideoAskResponse)
async def ask_about_video(video_id: str, payload: VideoAskRequest, db: AsyncSession = Depends(get_db)):
    """Answers a question using only this video's transcript, citing timestamps."""
    chunks = await _chunks_for(db, video_id)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="no transcript for this video; ingest captions first",
        )

    result = await answer_about_video(
        question=payload.question,
        video_title=chunks[0].video_title,
        chunks=[{"t_seconds": c.chunk_start_seconds, "text": c.chunk_text} for c in chunks],
    )
    return VideoAskResponse(**result)


@router.post("/topic/{topic_id}/flashcards", response_model=GeneratedCards)
async def flashcards_from_notes(
    topic_id: str, learner_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    """Generates FSRS flashcards from the learner's notes on a topic.

    Creates a synthetic Lesson to own the cards. Flashcard.lesson_id is a non-nullable FK, so a
    lesson-less card is not representable — and making the column nullable would be worse than
    this: recompute_mastery reaches a learner's flashcards by joining through Lesson.learner_id
    and Lesson.topic_id, so cards with no lesson would silently stop counting toward the
    flashcard component of mastery. Routing them through a real Lesson row means reviewing a
    note-derived card feeds mastery exactly like reviewing any other card, which is correct:
    the review is the demonstration, regardless of where the card came from.

    content_json records the provenance so the row is self-explanatory rather than looking like
    a lesson whose text went missing.
    """
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")

    notes = list(
        (
            await db.execute(
                select(VideoNote)
                .where(VideoNote.learner_id == learner_id, VideoNote.topic_id == topic_id)
                .order_by(VideoNote.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not notes:
        raise HTTPException(status_code=404, detail="no notes on this topic to generate from")

    cards = await cards_from_notes(
        topic.name,
        [
            {
                "t_seconds": n.t_seconds,
                "video_title": n.video_title,
                "learner_text": n.learner_text,
                "transcript_excerpt": n.transcript_excerpt,
            }
            for n in notes
        ],
    )
    if not cards:
        raise HTTPException(status_code=422, detail="notes produced no usable cards")

    lesson_id = str(uuid.uuid4())
    db.add(
        Lesson(
            id=lesson_id,
            topic_id=topic_id,
            learner_id=learner_id,
            content_json={
                "source": "video_notes",
                "topic_name": topic.name,
                "note_ids": [n.id for n in notes],
                "note_count": len(notes),
            },
        )
    )
    # Flush the parent before the children: no relationship() is declared between Lesson and
    # Flashcard, so SQLAlchemy won't order the cross-table inserts and the FK can be violated.
    # Same reason as the comment in orchestrator/nodes/stream_result.py.
    await db.flush()

    for card in cards:
        db.add(
            Flashcard(
                id=str(uuid.uuid4()),
                lesson_id=lesson_id,
                front=card["front"],
                back=card["back"],
                stability=card["stability"],
                difficulty=card["difficulty"],
                elapsed_days=card["elapsed_days"],
                # Set explicitly. stream_result.py omits this and so falls back to the column
                # default of "due now", discarding the interval it just computed.
                due_date=card["due_date"],
            )
        )

    await db.commit()
    return GeneratedCards(
        lesson_id=lesson_id, topic_id=topic_id, cards_created=len(cards), notes_used=len(notes)
    )
