import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.topic import EMBEDDING_DIM


class TutorProfile(Base):
    __tablename__ = "tutor_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    subjects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    specialty_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_tier: Mapped[str] = mapped_column(String, default="unverified")  # unverified|basic|background_checked
    response_time_percentile: Mapped[float] = mapped_column(Float, default=0.5)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    price_per_hour: Mapped[float] = mapped_column(Float, default=0.0)
    session_format: Mapped[str] = mapped_column(String, default="virtual")  # virtual|in_person|both


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tutor_id: Mapped[str] = mapped_column(String, ForeignKey("tutor_profiles.id"))
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    slot_start: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="hold")  # hold|confirmed|cancelled|expired
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionRecap(Base):
    __tablename__ = "session_recaps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String, ForeignKey("bookings.id"))
    summary: Mapped[str] = mapped_column(String)
    followup_card_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
