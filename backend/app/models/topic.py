import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

EMBEDDING_DIM = 384


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    content_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    # [{id, sub_concept, misconception_prompt, keywords}] — feeds Protégé Mode's persona
    # (Section 9); null/empty means the topic can't drive Protégé Mode yet.
    common_misconceptions: Mapped[list | None] = mapped_column(JSON, nullable=True)


class PrerequisiteEdge(Base):
    """Directed edge: prerequisite_topic_id must be mastered before topic_id."""

    __tablename__ = "prerequisite_edges"

    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), primary_key=True)
    prerequisite_topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), primary_key=True)


class MasteryScore(Base):
    """Rolling per-learner, per-topic mastery score (Section 4.7)."""

    __tablename__ = "mastery_scores"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"), primary_key=True)
    score: Mapped[float] = mapped_column(default=0.0)
