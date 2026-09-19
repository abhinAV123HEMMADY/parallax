"""Protégé Mode: the AI plays a confused student, seeded with a topic's real common
misconceptions, and the learner teaches it (Section 9 — Teach-the-AI Protégé Mode).

Leans on the protégé effect (teaching cements understanding better than re-reading) to
produce a mastery signal that's harder to fake than a quiz answer, since it requires
generating an explanation rather than recognizing a correct option.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, JSON, String
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
