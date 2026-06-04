"""Literature request/response schemas.

Pydantic models for the Agent-driven literature module: search (CNKI / PubMed /
both), detail, abstract translation (bilingual), MeSH term suggestion, and the
literature-collection CRUD (collections, folders, saved items).

Search results are *ephemeral* — they are produced live by the Agent (driving
the self-developed ``cnki-search`` MCP and the open-source ``pubmed-mcp-server``)
and are NOT persisted. Only collections (``LiteratureCollection`` /
``CollectionFolder`` / ``CollectedLiterature``) are stored, so the response
models mix Agent-derived shapes (``LiteratureRecord``, ``BilingualContent``)
with ORM-backed ones (``CollectionResponse`` and friends, using
``model_config = {"from_attributes": True}`` like ``app/schemas/analysis.py``).

Requirements: 10.1-10.46
"""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

# Default page size for search results (Requirement 10.5).
DEFAULT_PAGE_SIZE = 20

# Canonical data-source labels surfaced to the client (Requirement 10.22).
SOURCE_LABELS: dict[str, str] = {"cnki": "CNKI", "pubmed": "PubMed"}


# --- Search / detail -------------------------------------------------------


class LiteratureRecord(BaseModel):
    """A single literature record returned by search / detail.

    The shape mirrors the metadata the connectors return (Requirements 10.12,
    10.17): title, authors, journal, publication date, abstract, keywords, DOI,
    a data-source label ("CNKI" / "PubMed"), and an external id (PMID for
    PubMed). ``abstract_preview`` is the first 200 characters of the abstract
    for list display (Requirement 10.22).
    """

    title: str
    authors: list[str] = []
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    abstract: Optional[str] = None
    abstract_preview: Optional[str] = None
    keywords: list[str] = []
    doi: Optional[str] = None
    data_source: str
    external_id: Optional[str] = None
    citation_count: Optional[int] = None


class SearchRequest(BaseModel):
    """Request body for a literature search.

    ``sources`` selects the data source(s) — a subset of ``{"cnki", "pubmed"}``,
    defaulting to both (Requirements 10.6-10.8). ``page``/``page_size`` drive
    pagination (default 20/page, Requirement 10.5). ``sort_by`` is one of
    ``relevance`` (default), ``date``, or ``citations`` (Requirement 10.24).
    """

    keywords: str = ""
    author: Optional[str] = None
    journal: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    subject: Optional[str] = None
    sources: list[str] = ["cnki", "pubmed"]
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort_by: Optional[str] = None

    @field_validator("page")
    @classmethod
    def _page_min(cls, v: int) -> int:
        return 1 if v is None or v < 1 else v

    @field_validator("page_size")
    @classmethod
    def _page_size_bounds(cls, v: int) -> int:
        if v is None or v < 1:
            return DEFAULT_PAGE_SIZE
        return min(v, 100)


class SearchResponse(BaseModel):
    """Response schema for a literature search.

    ``results`` is the records for the requested page; ``total`` is the merged
    result count; ``totals`` is the per-source count keyed by data-source label
    (Requirement 10.28).
    """

    results: list[LiteratureRecord]
    page: int
    page_size: int
    total: int
    totals: dict[str, int]


# --- Translation (bilingual) ----------------------------------------------


class TranslateRequest(BaseModel):
    """Request body for translating a literature record's title + abstract.

    Search results are ephemeral, so the content to translate is supplied
    directly. The source language is inferred from ``source_language`` (``zh`` /
    ``en``) when given, else from ``source`` (``cnki`` ⇒ ``zh``, ``pubmed`` ⇒
    ``en``), else auto-detected from the text (Requirements 10.30, 10.31).
    """

    title: Optional[str] = None
    abstract: Optional[str] = None
    source: Optional[str] = None
    source_language: Optional[str] = None


class BilingualContentResponse(BaseModel):
    """Bilingual title/abstract content for the Bilingual_View (Req 10.30-10.34)."""

    original_title: Optional[str] = None
    translated_title: Optional[str] = None
    original_abstract: Optional[str] = None
    translated_abstract: Optional[str] = None
    source_language: str
    target_language: str


# --- MeSH suggestion -------------------------------------------------------


class MeshSuggestResponse(BaseModel):
    """Suggested MeSH terms for a PubMed query (Requirement 10.20)."""

    terms: list[str]


# --- Collections -----------------------------------------------------------


class CreateCollectionRequest(BaseModel):
    """Request body for creating a literature collection."""

    name: str


class FolderResponse(BaseModel):
    """Response schema for a collection folder (Requirement 10.39)."""

    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectedLiteratureResponse(BaseModel):
    """Response schema for a saved literature item (Requirements 10.37, 10.38)."""

    id: uuid.UUID
    collection_id: uuid.UUID
    folder_id: Optional[uuid.UUID] = None
    title: str
    authors: str
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    source: str
    external_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionResponse(BaseModel):
    """Response schema for a literature collection with its folders and items."""

    id: uuid.UUID
    name: str
    created_at: datetime
    folders: list[FolderResponse] = []
    items: list[CollectedLiteratureResponse] = []

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    """Response schema for the user's collections (sorted by date desc)."""

    collections: list[CollectionResponse]
    total: int


class CreateFolderRequest(BaseModel):
    """Request body for creating a folder under a collection."""

    collection_id: uuid.UUID
    name: str


class SaveLiteratureRequest(BaseModel):
    """Request body for saving a literature record into a collection.

    ``authors`` accepts either a list of names or a pre-joined string; it is
    normalised to a ``"; "``-joined string for storage (the model column is a
    single text field). ``source`` is the data-source label ("CNKI"/"PubMed" or
    "cnki"/"pubmed").
    """

    title: str
    authors: str = ""
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    source: str
    external_id: Optional[str] = None
    folder_id: Optional[uuid.UUID] = None

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_authors(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return "; ".join(str(x).strip() for x in v if str(x).strip())
        return str(v)
