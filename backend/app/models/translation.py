"""Translation models: TranslationRecord, TranslationResult."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class TranslationRecord(UUIDMixin, TimestampMixin, Base):
    """Translation record model."""

    __tablename__ = "translation_records"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    source_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    target_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="translation_records")
    result = relationship("TranslationResult", back_populates="translation", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_translation_records_user_id", "user_id"),
        Index("ix_translation_records_created_at", "created_at"),
    )


class TranslationResult(UUIDMixin, TimestampMixin, Base):
    """Translation result model."""

    __tablename__ = "translation_results"

    translation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("translation_records.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    original_paragraphs: Mapped[dict] = mapped_column(JSON, nullable=False)
    translated_paragraphs: Mapped[dict] = mapped_column(JSON, nullable=False)
    document_structure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    s3_key_pdf: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    s3_key_docx: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationships
    translation = relationship("TranslationRecord", back_populates="result")

    __table_args__ = (Index("ix_translation_results_translation_id", "translation_id"),)
