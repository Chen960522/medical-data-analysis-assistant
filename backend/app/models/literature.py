"""Literature models: LiteratureCollection, CollectionFolder, CollectedLiterature."""

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class LiteratureCollection(UUIDMixin, TimestampMixin, Base):
    """Literature collection model."""

    __tablename__ = "literature_collections"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    user = relationship("User", back_populates="literature_collections")
    folders = relationship("CollectionFolder", back_populates="collection", cascade="all, delete-orphan")
    items = relationship("CollectedLiterature", back_populates="collection", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_literature_collections_user_id", "user_id"),
        Index("ix_literature_collections_created_at", "created_at"),
    )


class CollectionFolder(UUIDMixin, TimestampMixin, Base):
    """Collection folder model."""

    __tablename__ = "collection_folders"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("literature_collections.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    collection = relationship("LiteratureCollection", back_populates="folders")
    items = relationship("CollectedLiterature", back_populates="folder")

    __table_args__ = (Index("ix_collection_folders_collection_id", "collection_id"),)


class CollectedLiterature(UUIDMixin, TimestampMixin, Base):
    """Collected literature item model."""

    __tablename__ = "collected_literature"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("literature_collections.id", ondelete="CASCADE"), nullable=False
    )
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("collection_folders.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[str] = mapped_column(Text, nullable=False)
    journal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'cnki' or 'pubmed'
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    collection = relationship("LiteratureCollection", back_populates="items")
    folder = relationship("CollectionFolder", back_populates="items")

    __table_args__ = (
        Index("ix_collected_literature_collection_id", "collection_id"),
        Index("ix_collected_literature_created_at", "created_at"),
    )
