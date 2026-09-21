from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    learner_id: str
    video_id: str
    video_title: str
    t_seconds: int = Field(ge=0)
    learner_text: str = Field(min_length=1)
    # An explicit topic always wins over the server's suggestion — the learner watching the
    # video knows what they're studying better than a similarity score does.
    topic_id: str | None = None
    # Opt-in per note. Default false: a note is private unless the learner says otherwise,
    # since the peer feed shows it to their connections.
    share: bool = False
    screenshot: str | None = None


class NoteOut(BaseModel):
    id: str
    video_id: str
    video_title: str
    topic_id: str | None
    topic_name: str | None = None
    t_seconds: int
    learner_text: str
    transcript_excerpt: str | None
    has_screenshot: bool
    created_at: datetime


class NoteDetail(NoteOut):
    """NoteOut plus the image. Separate because the timeline lists many notes and the
    screenshots are large — a list endpoint returning them would send megabytes to render a
    panel that only needs thumbnails on demand."""

    screenshot: str | None


class VideoNotePack(BaseModel):
    video_id: str
    video_title: str
    notes: list[NoteOut]


class TopicNotePack(BaseModel):
    topic_id: str
    topic_name: str
    # Ordered by prerequisite depth, so a course pack reads foundations-first rather than in
    # whatever order the learner happened to watch things.
    videos: list[VideoNotePack]


class CaptionCue(BaseModel):
    t_seconds: int = Field(ge=0)
    text: str


class TranscriptIngest(BaseModel):
    video_title: str
    cues: list[CaptionCue]


class TranscriptIngestResult(BaseModel):
    video_id: str
    cues_received: int
    chunks_written: int
    replaced_existing: bool


class TopicSuggestionOut(BaseModel):
    topic_id: str | None
    topic_name: str | None
    score: float
    strategy: str


class ProposedTopicOut(BaseModel):
    """The topic that saving a note would create, when neither matcher is confident.

    Reported by the GET so the panel can name the subject before anything is written — the
    endpoint stays a pure read, and creation stays on the POST that needs it.
    """

    name: str
    subject: str


class TopicSuggestionResponse(BaseModel):
    chosen: TopicSuggestionOut
    lexical: TopicSuggestionOut
    semantic: TopicSuggestionOut
    # Null whenever `chosen` matched an existing topic — there is nothing to create.
    proposed: ProposedTopicOut | None = None


class VideoAskRequest(BaseModel):
    question: str = Field(min_length=1)
    learner_id: str | None = None


class Citation(BaseModel):
    t_seconds: int
    quote: str


class VideoAskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    # True when the answer came from the deterministic fallback rather than a live model, so
    # the UI can be honest about it instead of presenting a keyword match as reasoning.
    stubbed: bool


class GeneratedCards(BaseModel):
    lesson_id: str
    topic_id: str
    cards_created: int
    notes_used: int
