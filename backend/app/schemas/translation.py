"""PDF translation request/response schemas.

Pydantic models for the Agent-driven PDF literature translation module
(Requirement 11): uploading a PDF, triggering full-document translation
(MarkItDown parse + Claude direct translation, orchestrated by the 「医析」
Agent), querying translation progress, fetching the bilingual Translation_Result,
downloading the exported document (PDF / Word, bilingual / translated-only),
and listing / deleting translation history.

ORM-backed response models use ``model_config = {"from_attributes": True}`` like
``app/schemas/data.py`` / ``app/schemas/analysis.py``. The bilingual result
arrays (``original_paragraphs`` / ``translated_paragraphs``) and the
``document_structure`` are persisted on :class:`app.models.translation.TranslationResult`.

Requirements: 11.1-11.50
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TranslationUploadResponse(BaseModel):
    """Response schema for a successful PDF upload (Requirement 11.7).

    Surfaces the file name, size, and (when known) page count alongside the
    record id and status so the client can confirm the upload.
    """

    id: uuid.UUID
    original_filename: str
    file_size: int
    page_count: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TranslateRequest(BaseModel):
    """Request body for triggering a full-document translation (Req 11.21).

    ``source_language`` optionally overrides the auto-detected document language
    (``zh`` / ``en``, Requirement 11.19); when omitted the Agent / Claude detects
    it. The target language is always the opposite of the source.
    """

    source_language: Optional[str] = None


class TranslationStatusResponse(BaseModel):
    """Response schema for translation progress (Requirements 11.28, 11.16-11.19)."""

    id: uuid.UUID
    status: str
    progress: Optional[float] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None

    model_config = {"from_attributes": True}


class TranslationResultResponse(BaseModel):
    """Response schema for the bilingual Translation_Result (Req 11.24, 11.30-11.34).

    Exposes the paragraph-level original/translated arrays and the preserved
    document structure that back the frontend's Bilingual_View.
    """

    id: uuid.UUID
    translation_id: uuid.UUID
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    status: str
    original_paragraphs: Any
    translated_paragraphs: Any
    document_structure: Optional[Any] = None


class TranslationDownloadResponse(BaseModel):
    """Response schema for a translation download request (Req 11.37-11.41).

    Returns a presigned URL the client can use to download the exported document
    from S3, together with the resolved ``format`` (``pdf`` / ``docx``) and
    ``mode`` (``bilingual`` / ``translation``).
    """

    download_url: str
    format: str
    mode: str


class TranslationHistoryItem(BaseModel):
    """A single translation-history entry (Requirements 11.43, 11.44)."""

    id: uuid.UUID
    original_filename: str
    file_size: int
    page_count: Optional[int] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TranslationHistoryResponse(BaseModel):
    """Response schema for the translation-history list (sorted by date desc)."""

    records: list[TranslationHistoryItem]
    total: int
