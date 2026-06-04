"""Tests for the CNKI client: response parsing and bounded retry/backoff.

No real network access occurs — fetchers are plain in-memory callables.
"""

from __future__ import annotations

import pytest

from cnki_search.client import (
    CNKIRequest,
    CNKIUnavailableError,
    fetch_with_retry,
    parse_response,
)


def _request() -> CNKIRequest:
    return CNKIRequest(keywords="糖尿病", page=1, page_size=20)


def test_parse_response_list_payload() -> None:
    payload = [
        {
            "title": "研究一",
            "abstract": "摘要一",
            "authors": ["张三"],
            "journal": "期刊A",
            "publication_date": "2022-01-01",
            "keywords": ["关键词"],
            "doi": "10.1/a",
        }
    ]
    records, total = parse_response(payload)
    assert total is None
    assert len(records) == 1
    assert records[0].title == "研究一"
    assert records[0].data_source == "CNKI"


def test_parse_response_envelope_with_total() -> None:
    payload = {
        "total": 137,
        "records": [
            {"title": "研究二", "authors": "李四；王五"},
            {"title": "研究三"},
        ],
    }
    records, total = parse_response(payload)
    assert total == 137
    assert [r.title for r in records] == ["研究二", "研究三"]
    assert records[0].authors == ["李四", "王五"]


def test_parse_response_none_and_unknown_types() -> None:
    assert parse_response(None) == ([], None)
    assert parse_response(12345) == ([], None)


def test_fetch_with_retry_returns_first_success() -> None:
    calls: list[int] = []

    def fetcher(req: CNKIRequest):
        calls.append(1)
        return [{"title": "ok"}]

    result = fetch_with_retry(_request(), fetcher, sleep=lambda _s: None)
    assert result == [{"title": "ok"}]
    assert len(calls) == 1


def test_fetch_with_retry_recovers_after_transient_failures() -> None:
    attempts: list[int] = []

    def flaky(req: CNKIRequest):
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("transient")
        return [{"title": "recovered"}]

    result = fetch_with_retry(_request(), flaky, max_retries=3, sleep=lambda _s: None)
    assert result == [{"title": "recovered"}]
    assert len(attempts) == 3


def test_fetch_with_retry_raises_unavailable_after_exhaustion() -> None:
    attempts: list[int] = []

    def always_fails(req: CNKIRequest):
        attempts.append(1)
        raise TimeoutError("down")

    with pytest.raises(CNKIUnavailableError) as exc_info:
        fetch_with_retry(_request(), always_fails, max_retries=3, sleep=lambda _s: None)

    # Bounded retries: exactly max_retries attempts, no more.
    assert len(attempts) == 3
    assert exc_info.value.attempts == 3
    # User-facing message mentions retrying / switching to PubMed (Requirement 10.11).
    assert "PubMed" in str(exc_info.value)


def test_fetch_with_retry_uses_bounded_exponential_backoff() -> None:
    delays: list[float] = []

    def always_fails(req: CNKIRequest):
        raise ConnectionError("nope")

    with pytest.raises(CNKIUnavailableError):
        fetch_with_retry(
            _request(),
            always_fails,
            max_retries=3,
            backoff_base=0.5,
            sleep=delays.append,
        )

    # One sleep between each of the 3 attempts (i.e. 2 sleeps), exponential.
    assert delays == [0.5, 1.0]


def test_fetch_with_retry_passes_through_unavailable_error_immediately() -> None:
    attempts: list[int] = []

    def fetcher(req: CNKIRequest):
        attempts.append(1)
        raise CNKIUnavailableError()

    with pytest.raises(CNKIUnavailableError):
        fetch_with_retry(_request(), fetcher, max_retries=3, sleep=lambda _s: None)

    # A definitive unavailable signal is not retried.
    assert len(attempts) == 1
