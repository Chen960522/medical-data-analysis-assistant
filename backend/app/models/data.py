"""DataFile model."""

import uuid
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class DataFile(UUIDMixin, TimestampMixin, Base):
    """Uploaded data file model."""

    __tablename__ = "data_files"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)

    # Relationships
    user = relationship("User", back_populates="data_files")
    analysis_sessions = relationship("AnalysisSession", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_data_files_user_id", "user_id"),
        Index("ix_data_files_created_at", "created_at"),
    )
