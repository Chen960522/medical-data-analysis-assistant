"""Analysis models: AnalysisSession, AnalysisResult, AnalysisDimension, Chart."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class AnalysisSession(UUIDMixin, TimestampMixin, Base):
    """Analysis session model."""

    __tablename__ = "analysis_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_files.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="analysis_sessions")
    file = relationship("DataFile", back_populates="analysis_sessions")
    results = relationship("AnalysisResult", back_populates="session", cascade="all, delete-orphan")
    dimensions = relationship("AnalysisDimension", back_populates="session", cascade="all, delete-orphan")
    charts = relationship("Chart", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="session", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="analysis_session")

    __table_args__ = (
        Index("ix_analysis_sessions_user_id", "user_id"),
        Index("ix_analysis_sessions_created_at", "created_at"),
    )


class AnalysisResult(UUIDMixin, TimestampMixin, Base):
    """Analysis result model."""

    __tablename__ = "analysis_results"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False
    )
    result_type: Mapped[str] = mapped_column(String(100), nullable=False)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Relationships
    session = relationship("AnalysisSession", back_populates="results")

    __table_args__ = (Index("ix_analysis_results_session_id", "session_id"),)


class AnalysisDimension(UUIDMixin, TimestampMixin, Base):
    """Analysis dimension model."""

    __tablename__ = "analysis_dimensions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'system' or 'user'
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    session = relationship("AnalysisSession", back_populates="dimensions")

    __table_args__ = (Index("ix_analysis_dimensions_session_id", "session_id"),)


class Chart(UUIDMixin, TimestampMixin, Base):
    """Generated chart model."""

    __tablename__ = "charts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False
    )
    chart_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    echarts_option: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Relationships
    session = relationship("AnalysisSession", back_populates="charts")

    __table_args__ = (Index("ix_charts_session_id", "session_id"),)
