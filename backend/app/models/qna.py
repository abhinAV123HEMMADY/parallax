import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QnaPost(Base):
    __tablename__ = "qna_posts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    author_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(String)
    moderation_status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    source: Mapped[str] = mapped_column(String, default="learner")  # learner|protege_explanation
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MentorProfile(Base):
    """Opt-in, unpaid, informal peer-mentor flag — distinct from the vetted tutor pool (Section 7.4)."""

    __tablename__ = "mentor_profiles"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), primary_key=True)
    mastery_score: Mapped[float] = mapped_column(Float)
