"""CNKI HTTP access and response parsing with bounded retry/timeout.

CNKI (China National Knowledge Infrastructure) has no standard public API, so
this module encapsulates the network access behind a small, injectable
``Fetcher`` callable and parses the returned payload into
:class:`~cnki_search.models.LiteratureRecord` objects.

Design goals:

* Importing this module MUST NOT require network access or a live CNKI service.
* The actual network call is performed by an injectable ``Fetcher`` so tests can
  run a fake fetcher with no real HTTP traffic.
* A bounded retry loop with exponential backoff wraps the fetch; on persistent
  failure a :class:`CNKIUnavailableError` is raised carrying a clear, user-facing
  message instructing the user to retry later or switch to PubMed
  (Requirement 10.11).
* The parser is tolerant of both a structured JSON payload (a list of records or
  a ``{"records": [...], "total": N}`` envelope) and an HTML result page, which
  it scrapes with BeautifulSoup when available.

Requirements: 10.9, 10.10, 10.11, 10.12
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .models import LiteratureRecord

# A Fetcher takes the request parameters and returns a raw payload (parsed JSON
# object/list, or an HTML/text string) for the parser to consume.
Fetcher = Callable[["CNKIRequest"], Any]

# Default request budget. CNKI must return within 10 seconds (Requirement
# 10.10); the per-attempt timeout plus retries is kept comfortably under that.
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5

# User-facing message surfaced when CNKI cannot be reached (Requirement 10.11).
CNKI_UNAVAILABLE_MESSAGE = (
    "CNKI 服务暂时不可用，请稍后重试或切换到 PubMed 数据源。 "
    "(CNKI service is temporarily unavailable. Please retry later or switch to PubMed.)"
)


class CNKIUnavailableError(RuntimeError):
    """Raised when CNKI cannot be reached after exhausting all retries.

    Requirement 10.11: surface a clear message that CNKI is temporarily
    unavailable and suggest retrying later or switching to PubMed.
    """

    def __init__(self, message: str = CNKI_UNAVAILABLE_MESSAGE, *, attempts: int = 0):
        super().__init__(message)
        self.attempts = attempts


class CNKIRequest:
    """The normalized parameters for a single CNKI search request."""

    __slots__ = ("keywords", "author", "journal", "date_from", "date_to", "page", "page_size")

    def __init__(
        self,
        keywords: str,
        author: str = "",
        journal: str = "",
        date_from: str = "",
        date_to: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        self.keywords = keywords
        self.author = author
        self.journal = journal
        self.date_from = date_from
        self.date_to = date_to
        self.page = page
        self.page_size = page_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "keywords": self.keywords,
            "author": self.author,
            "journal": self.journal,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "page": self.page,
            "page_size": self.page_size,
        }


def fetch_with_retry(
    request: CNKIRequest,
    fetcher: Fetcher,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Invoke ``fetcher`` with bounded retries and exponential backoff.

    Args:
        request: The normalized CNKI request.
        fetcher: Callable performing the actual network access.
        max_retries: Maximum number of attempts (must be >= 1).
        backoff_base: Base seconds for exponential backoff between attempts.
        sleep: Injectable sleep function (overridable in tests).

    Returns:
        The raw payload returned by ``fetcher``.

    Raises:
        CNKIUnavailableError: If every attempt fails (Requirement 10.11).
    """
    attempts = max(1, int(max_retries))
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            return fetcher(request)
        except CNKIUnavailableError:
            # Already a clear, user-facing failure — re-raise as-is.
            raise
        except Exception as exc:  # noqa: BLE001 - any network/parse error is retryable
            last_exc = exc
            if attempt < attempts - 1:
                # Exponential backoff: base * 2**attempt.
                sleep(backoff_base * (2**attempt))

    raise CNKIUnavailableError(attempts=attempts) from last_exc


# --- Response parsing ------------------------------------------------------


def parse_response(payload: Any) -> tuple[list[LiteratureRecord], int | None]:
    """Parse a raw CNKI payload into records and an optional total count.

    Supports:
        * A list of record dicts.
        * An envelope dict ``{"records"/"results"/"data": [...], "total": N}``.
        * An HTML/text string (scraped via BeautifulSoup when available).

    Args:
        payload: The raw payload returned by the fetcher.

    Returns:
        Tuple of ``(records, total)``. ``total`` is ``None`` when the payload
        does not report an explicit total result count.
    """
    if payload is None:
        return [], None

    if isinstance(payload, list):
        return [LiteratureRecord.from_dict(item) for item in payload if isinstance(item, dict)], None

    if isinstance(payload, dict):
        raw_records = _first_list(payload, "records", "results", "data", "items")
        records = [LiteratureRecord.from_dict(item) for item in raw_records if isinstance(item, dict)]
        total = _coerce_total(payload.get("total", payload.get("total_count", payload.get("count"))))
        return records, total

    if isinstance(payload, str):
        return _parse_html(payload), None

    return [], None


def _parse_html(html: str) -> list[LiteratureRecord]:
    """Scrape literature records from a CNKI HTML result page.

    Uses BeautifulSoup when available. Each result row is expected to carry
    ``data-*`` attributes (or nested elements) describing the record; the parser
    is defensive and skips rows it cannot interpret.
    """
    try:
        from bs4 import BeautifulSoup  # lazy import: optional dependency
    except Exception:  # pragma: no cover - depends on optional dep
        return []

    soup = BeautifulSoup(html, "html.parser")
    records: list[LiteratureRecord] = []

    for row in soup.select(".result-item, .literature-item, tr.result"):
        record = _record_from_element(row)
        if record is not None:
            records.append(record)

    return records


def _record_from_element(row: Any) -> LiteratureRecord | None:
    """Build a record from a BeautifulSoup result element, or ``None``."""

    def text_of(selector: str) -> str:
        node = row.select_one(selector)
        return node.get_text(strip=True) if node is not None else ""

    def attr_or_text(attr: str, selector: str) -> str:
        if row.has_attr(attr):
            return str(row[attr]).strip()
        return text_of(selector)

    title = attr_or_text("data-title", ".title")
    if not title:
        return None

    return LiteratureRecord.from_dict(
        {
            "title": title,
            "abstract": attr_or_text("data-abstract", ".abstract"),
            "authors": attr_or_text("data-authors", ".authors"),
            "journal": attr_or_text("data-journal", ".journal"),
            "publication_date": attr_or_text("data-date", ".date"),
            "keywords": attr_or_text("data-keywords", ".keywords"),
            "doi": attr_or_text("data-doi", ".doi"),
        }
    )


# --- HTTP fetcher (lazy httpx) ---------------------------------------------


def http_fetcher(
    base_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
) -> Fetcher:
    """Build a real HTTP fetcher backed by httpx.

    ``httpx`` is imported lazily so that importing this module (and running the
    pure unit tests) does not require httpx to be installed.

    Args:
        base_url: CNKI search endpoint URL.
        timeout: Per-request timeout in seconds.
        headers: Optional extra request headers.

    Returns:
        A ``Fetcher`` callable suitable for :func:`fetch_with_retry`.
    """

    def _fetch(request: CNKIRequest) -> Any:
        try:
            import httpx  # lazy import: optional at module import time
        except Exception as exc:  # pragma: no cover - optional dep
            raise RuntimeError("httpx is not available. Install 'httpx' to enable CNKI HTTP access.") from exc

        response = httpx.get(base_url, params=request.to_dict(), timeout=timeout, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    return _fetch


# --- Small helpers ---------------------------------------------------------


def _first_list(source: dict[str, Any], *keys: str) -> list[Any]:
    """Return the first value among ``keys`` that is a list."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return value
    return []


def _coerce_total(value: Any) -> int | None:
    """Coerce a reported total count to a non-negative int, or ``None``."""
    if value is None:
        return None
    try:
        total = int(value)
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None
