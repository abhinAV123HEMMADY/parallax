import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.topic import EMBEDDING_DIM


class VideoTranscriptChunk(Base):
    """Backs the Video Transcript MCP server's search_transcripts tool (Section 5.1)."""

    __tablename__ = "video_transcript_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String)
    video_title: Mapped[str] = mapped_column(String)
    chunk_start_seconds: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(String)
    difficulty_level: Mapped[str] = mapped_column(String, default="intro")  # intro|intermediate|advanced
    chunk_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
