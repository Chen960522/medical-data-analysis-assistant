"""Report model."""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Report(UUIDMixin, TimestampMixin, Base):
    """Generated report model."""

    __tablename__ = "reports"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    s3_key_pdf: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    s3_key_docx: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationships
    session = relationship("AnalysisSession", back_populates="reports")
    user = relationship("User", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_user_id", "user_id"),
        Index("ix_reports_session_id", "session_id"),
        Index("ix_reports_created_at", "created_at"),
    )
