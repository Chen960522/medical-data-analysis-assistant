"""Data models for CNKI literature search.

Defines :class:`LiteratureRecord` — a single literature record retrieved from
CNKI (China National Knowledge Infrastructure) — carrying the metadata required
by the spec: title, abstract, authors, journal name, publication date,
keywords, and DOI (Requirement 10.12). Every record is tagged with the
``data_source`` label ``"CNKI"`` so merged result lists can be filtered by
source.

Requirements: 10.12
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Data source label for records produced by this server (Requirement 10.12 /
# the Data_Source_Label concept in the requirements).
DATA_SOURCE_CNKI = "CNKI"


@dataclass
class LiteratureRecord:
    """A single literature record retrieved from CNKI.

    Attributes:
        title: Literature title.
        abstract: Abstract / summary text.
        authors: Ordered list of author names.
        journal: Journal (or other source) name.
        publication_date: Publication date as ``YYYY-MM-DD`` (or a partial date
            such as ``YYYY`` / ``YYYY-MM`` when only that precision is known).
        keywords: List of keyword terms.
        doi: Digital Object Identifier, when available.
        data_source: Source label, always ``"CNKI"`` for this server.
    """

    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    publication_date: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    data_source: str = DATA_SOURCE_CNKI

    def to_dict(self) -> dict[str, Any]:
        """Serialize the record to a JSON-compatible dictionary."""
        return {
            "title": self.title,
            "abstract": self.abstract,
            "authors": list(self.authors),
            "journal": self.journal,
            "publication_date": self.publication_date,
            "keywords": list(self.keywords),
            "doi": self.doi,
            "data_source": self.data_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LiteratureRecord":
        """Build a record from a loosely-typed mapping, normalizing fields.

        Tolerates common key aliases and coerces ``authors`` / ``keywords`` from
        either a list or a delimited string into a clean list of strings.
        """
        return cls(
            title=_as_str(_first(data, "title", "name")),
            abstract=_as_str(_first(data, "abstract", "summary", "description")),
            authors=_as_str_list(_first(data, "authors", "author")),
            journal=_as_str(_first(data, "journal", "journal_name", "source")),
            publication_date=_normalize_date(_first(data, "publication_date", "date", "pub_date", "year")),
            keywords=_as_str_list(_first(data, "keywords", "keyword")),
            doi=_as_str(_first(data, "doi", "DOI")),
            data_source=_as_str(data.get("data_source")) or DATA_SOURCE_CNKI,
        )


# --- Normalization helpers -------------------------------------------------


def _first(source: dict[str, Any], *keys: str) -> Any:
    """Return the first present, non-None value among ``keys`` in ``source``."""
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _as_str(value: Any) -> str:
    """Coerce a scalar value to a stripped string (``None`` -> empty)."""
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    """Coerce ``value`` into a clean list of non-empty strings.

    Accepts a list/tuple of items, or a single string with common delimiters
    (``;``, ``,``, ``、``, ``/``). ``None`` yields an empty list.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = text.replace("；", ";").replace("，", ",").replace("、", ";").replace("/", ";")
    for delimiter in (";", ","):
        parts = parts.replace(delimiter, "\u0000")
    return [segment.strip() for segment in parts.split("\u0000") if segment.strip()]


def _normalize_date(value: Any) -> str:
    """Normalize a publication date to a string.

    Integers and bare years are returned as strings; other values are stripped.
    The function is intentionally lenient — CNKI surfaces dates in a variety of
    precisions (year only, year-month, full date).
    """
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return str(value).strip()
