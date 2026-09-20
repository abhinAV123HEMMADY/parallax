"""Protégé Mode: the AI plays a confused student, seeded with a topic's real common
misconceptions, and the learner teaches it (Section 9 — Teach-the-AI Protégé Mode).

Leans on the protégé effect (teaching cements understanding better than re-reading) to
produce a mastery signal that's harder to fake than a quiz answer, since it requires
generating an explanation rather than recognizing a correct option.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProtegeSession(Base):
    __tablename__ = "protege_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    transcript_json: Mapped[list] = mapped_column(JSON, default=list)
    understanding_score: Mapped[float] = mapped_column(Float, default=0.0)
    misconceptions_resolved: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[str] = mapped_column(String, default="active")  # active|completed|published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProtegeConcession(Base):
    """A misconception the persona explained itself after the learner punted twice.

    Kept apart from ProtegeSession.misconceptions_resolved on purpose: both close the
    misconception so the conversation can move on, but only resolved ones are taught, and
    only taught ones count toward the understanding score. Conflating them let a learner
    answer "I don't know" repeatedly and finish with a passing score.

    Its own table rather than a column because the schema comes from create_all, which adds
    missing tables but never missing columns.
    """

    __tablename__ = "protege_concessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("protege_sessions.id"))
    misconception_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProtegeRecap(Base):
    """A finished session's recap, written once when the session clears the threshold.

    Separate table rather than columns on ProtegeSession because the schema is created with
    Base.metadata.create_all, which adds missing tables but never missing columns — a new
    column would silently not exist on any database that already has the old table.
    """

    __tablename__ = "protege_recaps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("protege_sessions.id"), unique=True)
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    summary: Mapped[str] = mapped_column(String)
    taught_well: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    still_shaky: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    understanding_score: Mapped[float] = mapped_column(Float, default=0.0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
