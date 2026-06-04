"""MCP server exposing the CNKI literature-search tool.

This module is a thin layer over the network/parse logic in
:mod:`cnki_search.client`.

Design goals (mirroring the report-generation server):

* Importing this module MUST NOT require the ``mcp`` package, network access, or
  a live CNKI service. The MCP runtime (``FastMCP``) is imported lazily inside
  :func:`create_server`; the HTTP fetcher imports httpx lazily.
* The actual tool logic lives in the plain :func:`search_cnki_impl` function so
  it can be unit tested directly. The ``@server.tool()`` wrapper registered in
  :func:`create_server` simply delegates to it.
* The CNKI network access is injected via :func:`configure` (a fetcher callable),
  so the tool never hard-depends on a live service and tests can run with a fake
  fetcher.

Tool:
    ``search_cnki(keywords, author="", journal="", date_from="", date_to="",
                  page=1, page_size=20) -> str``
        Returns a JSON string with the matched literature records and pagination
        info.

Requirements: 10.9, 10.10, 10.11, 10.12, 10.13
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from .client import (
    DEFAULT_BACKOFF_BASE_SECONDS,
    DEFAULT_MAX_RETRIES,
    CNKIRequest,
    CNKIUnavailableError,
    Fetcher,
    fetch_with_retry,
    parse_response,
)

SERVER_NAME = "cnki-search"

# Default look-back window: the most recent 5 years (Requirement 10.13).
DEFAULT_LOOKBACK_YEARS = 5

# Pagination guards.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# --- Module-level, injectable configuration -------------------------------

_fetcher: Fetcher | None = None
_max_retries: int = DEFAULT_MAX_RETRIES
_backoff_base: float = DEFAULT_BACKOFF_BASE_SECONDS


def configure(
    *,
    fetcher: Fetcher | None = None,
    max_retries: int | None = None,
    backoff_base: float | None = None,
) -> None:
    """Wire integration hooks used by the tool implementation.

    Args:
        fetcher: Callable that performs the actual CNKI network access, taking a
            :class:`~cnki_search.client.CNKIRequest` and returning a raw payload
            (JSON object/list or HTML string). When not configured,
            :func:`search_cnki_impl` raises a clear error instructing the caller
            to configure a fetcher.
        max_retries: Maximum number of fetch attempts before failing.
        backoff_base: Base seconds for exponential backoff between attempts.
    """
    global _fetcher, _max_retries, _backoff_base
    if fetcher is not None:
        _fetcher = fetcher
    if max_retries is not None:
        _max_retries = max(1, int(max_retries))
    if backoff_base is not None:
        _backoff_base = max(0.0, float(backoff_base))


def reset() -> None:
    """Reset injectable state (test helper)."""
    global _fetcher, _max_retries, _backoff_base
    _fetcher = None
    _max_retries = DEFAULT_MAX_RETRIES
    _backoff_base = DEFAULT_BACKOFF_BASE_SECONDS


# --- Tool implementation (directly unit-testable) --------------------------


def search_cnki_impl(
    keywords: str,
    author: str = "",
    journal: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    page_size: int = 20,
    *,
    fetcher: Fetcher | None = None,
    today: _dt.date | None = None,
) -> str:
    """Search CNKI medical literature and return a JSON payload.

    Applies a default time range of the most recent 5 years when ``date_from``
    is not provided (Requirement 10.13), executes the (injectable) fetch with
    bounded retry/backoff (Requirement 10.10/10.11), parses the response into
    literature records carrying the required metadata (Requirement 10.12), and
    returns a JSON string with the records plus pagination info.

    Args:
        keywords: Search keywords (Chinese or English).
        author: Optional author-name filter.
        journal: Optional journal-name filter.
        date_from: Start date ``YYYY-MM-DD`` (defaults to 5 years ago).
        date_to: End date ``YYYY-MM-DD`` (defaults to today).
        page: 1-based page number.
        page_size: Results per page (clamped to ``[1, MAX_PAGE_SIZE]``).
        fetcher: Optional fetcher override (defaults to the configured one).
        today: Optional reference date for the default range (testing hook).

    Returns:
        A JSON string ``{"query", "page", "page_size", "total", "count",
        "results": [...]}``.

    Raises:
        CNKIUnavailableError: If CNKI cannot be reached after all retries
            (Requirement 10.11).
        RuntimeError: If no fetcher has been configured.
    """
    active_fetcher = fetcher or _fetcher
    if active_fetcher is None:
        raise RuntimeError(
            "No CNKI fetcher configured. Call configure(fetcher=...) before searching, "
            "or pass fetcher= to search_cnki_impl()."
        )

    norm_page = _normalize_page(page)
    norm_page_size = _normalize_page_size(page_size)
    resolved_from, resolved_to = _resolve_date_range(date_from, date_to, today=today)

    request = CNKIRequest(
        keywords=(keywords or "").strip(),
        author=(author or "").strip(),
        journal=(journal or "").strip(),
        date_from=resolved_from,
        date_to=resolved_to,
        page=norm_page,
        page_size=norm_page_size,
    )

    payload = fetch_with_retry(
        request,
        active_fetcher,
        max_retries=_max_retries,
        backoff_base=_backoff_base,
    )
    records, total = parse_response(payload)

    result = {
        "query": {
            "keywords": request.keywords,
            "author": request.author,
            "journal": request.journal,
            "date_from": request.date_from,
            "date_to": request.date_to,
        },
        "page": norm_page,
        "page_size": norm_page_size,
        "total": total,
        "count": len(records),
        "results": [record.to_dict() for record in records],
    }
    return json.dumps(result, ensure_ascii=False)


# --- Internal helpers ------------------------------------------------------


def _normalize_page(page: Any) -> int:
    """Clamp the page number to a 1-based positive integer."""
    try:
        value = int(page)
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


def _normalize_page_size(page_size: Any) -> int:
    """Clamp the page size to ``[1, MAX_PAGE_SIZE]``."""
    try:
        value = int(page_size)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    if value < 1:
        return DEFAULT_PAGE_SIZE
    return min(value, MAX_PAGE_SIZE)


def _resolve_date_range(
    date_from: str,
    date_to: str,
    *,
    today: _dt.date | None = None,
) -> tuple[str, str]:
    """Resolve the effective date range, defaulting to the most recent 5 years.

    Requirement 10.13: retrieve the latest literature within the most recent 5
    years by default, with the option to adjust the time range. When the caller
    supplies ``date_from`` / ``date_to`` they are honored as-is; otherwise the
    range defaults to ``[today - 5 years, today]``.

    Args:
        date_from: Caller-supplied start date (``YYYY-MM-DD``) or empty.
        date_to: Caller-supplied end date (``YYYY-MM-DD``) or empty.
        today: Reference "today" date (defaults to the real current date).

    Returns:
        Tuple ``(date_from, date_to)`` as ``YYYY-MM-DD`` strings.
    """
    reference = today or _dt.date.today()

    resolved_to = (date_to or "").strip()
    if not resolved_to:
        resolved_to = reference.isoformat()

    resolved_from = (date_from or "").strip()
    if not resolved_from:
        # Subtract 5 years, guarding against Feb-29 reference dates.
        try:
            start = reference.replace(year=reference.year - DEFAULT_LOOKBACK_YEARS)
        except ValueError:
            start = reference.replace(year=reference.year - DEFAULT_LOOKBACK_YEARS, day=28)
        resolved_from = start.isoformat()

    return resolved_from, resolved_to


# --- MCP server factory ----------------------------------------------------


def create_server():
    """Create and configure the FastMCP server instance.

    ``mcp`` is imported lazily here so that importing this module (and running
    the pure unit tests) does not require the MCP runtime to be installed.

    Returns:
        A configured ``FastMCP`` server exposing the ``search_cnki`` tool.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'mcp' package is required to run the cnki-search server. Install it with 'pip install mcp'."
        ) from exc

    server = FastMCP(SERVER_NAME)

    @server.tool()
    async def search_cnki(
        keywords: str,
        author: str = "",
        journal: str = "",
        date_from: str = "",
        date_to: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """搜索 CNKI（中国知网）医学文献。

        Args:
            keywords: 搜索关键词（支持中英文）。
            author: 作者名筛选。
            journal: 期刊名筛选。
            date_from: 起始日期 (YYYY-MM-DD)，默认最近 5 年。
            date_to: 结束日期 (YYYY-MM-DD)，默认今天。
            page: 页码。
            page_size: 每页结果数。

        Returns:
            JSON 格式的文献列表，包含标题、摘要、作者、期刊、发表日期、关键词、DOI
            等元数据，以及分页信息。CNKI 不可用时返回明确的错误提示，建议稍后重试或
            切换到 PubMed。
        """
        try:
            return search_cnki_impl(
                keywords,
                author=author,
                journal=journal,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
            )
        except CNKIUnavailableError as exc:
            return json.dumps(
                {"error": "cnki_unavailable", "message": str(exc), "results": []},
                ensure_ascii=False,
            )

    return server
