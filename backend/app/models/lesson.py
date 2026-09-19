import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    content_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id"))
    question: Mapped[str] = mapped_column(String)
    correct: Mapped[bool] = mapped_column(Boolean)
    modality_used: Mapped[str | None] = mapped_column(String, nullable=True)  # analogy | diagram | video


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(String, ForeignKey("lessons.id"))
    front: Mapped[str] = mapped_column(String)
    back: Mapped[str] = mapped_column(String)
    stability: Mapped[float] = mapped_column(Float, default=1.0)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConfidenceRating(Base):
    __tablename__ = "confidence_ratings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    card_id: Mapped[str] = mapped_column(String, ForeignKey("flashcards.id"))
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)  # 0-5, pre-reveal self-rating
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
