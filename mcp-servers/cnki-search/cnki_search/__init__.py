"""CNKI Search MCP Server package.

Searches CNKI (China National Knowledge Infrastructure / 中国知网) for medical
literature and returns records carrying the required metadata: title, abstract,
authors, journal name, publication date, keywords, and DOI.

CNKI has no standard public API, so :mod:`cnki_search.client` encapsulates the
network access behind an injectable ``Fetcher`` callable with bounded
retry/backoff and a clear "temporarily unavailable" failure mode. The search
logic (:mod:`cnki_search.server`) is a thin, unit-testable layer over the
client; the MCP runtime and httpx are imported lazily so the package and its
pure unit tests do not require those dependencies.

Requirements: 10.9-10.13
"""

from .models import DATA_SOURCE_CNKI, LiteratureRecord
from .client import (
    CNKI_UNAVAILABLE_MESSAGE,
    CNKIRequest,
    CNKIUnavailableError,
    fetch_with_retry,
    http_fetcher,
    parse_response,
)
from .server import configure, reset, search_cnki_impl

__all__ = [
    "DATA_SOURCE_CNKI",
    "LiteratureRecord",
    "CNKI_UNAVAILABLE_MESSAGE",
    "CNKIRequest",
    "CNKIUnavailableError",
    "fetch_with_retry",
    "http_fetcher",
    "parse_response",
    "configure",
    "reset",
    "search_cnki_impl",
]
