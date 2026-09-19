import uuid

from sqlalchemy import ARRAY, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    grade_level: Mapped[str | None] = mapped_column(String, nullable=True)
    goals: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
