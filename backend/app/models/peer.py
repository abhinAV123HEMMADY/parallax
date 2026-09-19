import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Connection(Base):
    """Peer graph edge (MVP substitute for Neo4j, Section 9.3)."""

    __tablename__ = "connections"

    user_id_a: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    user_id_b: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|connected


class StruggleEvent(Base):
    __tablename__ = "struggle_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    signal_type: Mapped[str] = mapped_column(String)  # low_confidence_correct|quiz_miss|flashcard_lapse|prerequisite_gap
    severity: Mapped[float] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(String, default="private")  # private|connections|cohort
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudySquad(Base):
    """Auto-formed when 3+ connected learners share an unresolved struggle signal (Section 7.3)."""

    __tablename__ = "study_squads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String, ForeignKey("topics.id"))
    member_ids: Mapped[list[str]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
