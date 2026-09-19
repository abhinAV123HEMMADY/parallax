import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VideoNote(Base):
    """A moment a learner marked while watching a video, captured by the Chrome extension.

    The note is anchored to a playback second rather than to a lesson, because the learner is
    on YouTube when they take it — there may be no Mentra lesson in play at all. `topic_id` is
    therefore nullable: a note on an arbitrary video is only mapped to a topic when the
    suggestion in routes_notes clears its confidence threshold, or when the learner picks one.
    An unmapped note is a first-class outcome, not a failure — it still renders in the timeline
    and exports to PDF; it just doesn't feed the peer layer.

    `transcript_excerpt` is resolved server-side from the ingested caption track rather than
    trusted from the client, so what a note claims was being said at that second is always
    something the backend can stand behind.
    """

    __tablename__ = "video_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    video_id: Mapped[str] = mapped_column(String)  # YouTube's 11-char id, not a Mentra id
    video_title: Mapped[str] = mapped_column(String)
    topic_id: Mapped[str | None] = mapped_column(String, ForeignKey("topics.id"), nullable=True)
    t_seconds: Mapped[int] = mapped_column(Integer)
    learner_text: Mapped[str] = mapped_column(Text)
    transcript_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A cropped, downscaled JPEG data URL from chrome.tabs.captureVisibleTab — the one thing a
    # web page cannot produce, since a cross-origin iframe taints the canvas.
    #
    # Storing image bytes in a text column is the wrong long-term answer: it inflates every row
    # read that doesn't need the image, and Postgres is not a CDN. The right answer is object
    # storage with the row holding a signed URL. It is done this way here because it keeps the
    # whole feature to one datastore, and it is made survivable by a hard size cap enforced in
    # routes_notes (MAX_SCREENSHOT_BYTES) plus downscaling in the extension before upload.
    screenshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # The two read paths: one video's timeline (the panel) and one topic's notes across
        # videos (the course-pack PDF and the flashcard generator).
        Index("ix_video_notes_learner_video", "learner_id", "video_id"),
        Index("ix_video_notes_learner_topic", "learner_id", "topic_id"),
    )
