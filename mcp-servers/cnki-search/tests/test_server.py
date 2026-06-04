"""Tests for the search_cnki tool implementation.

These exercise ``search_cnki_impl`` directly (the ``@server.tool()`` wrapper
delegates to it). Importing :mod:`cnki_search.server` must not require the
``mcp`` package or network access; all fetches use an injected fake fetcher.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from cnki_search import server
from cnki_search.client import CNKIRequest, CNKIUnavailableError


@pytest.fixture(autouse=True)
def _reset_server_state():
    """Reset injectable server state before and after each test."""
    server.reset()
    yield
    server.reset()


def _fake_records() -> list[dict]:
    return [
        {
            "title": "2 型糖尿病的临床研究",
            "abstract": "本研究探讨了……",
            "authors": ["张三", "李四"],
            "journal": "中华内分泌代谢杂志",
            "publication_date": "2023-06-15",
            "keywords": ["2型糖尿病", "血糖控制"],
            "doi": "10.3760/cma.j.123",
        }
    ]


def test_search_parses_mocked_response_into_records_with_all_metadata() -> None:
    def fetcher(req: CNKIRequest):
        return {"total": 1, "records": _fake_records()}

    out = server.search_cnki_impl("糖尿病", fetcher=fetcher)
    payload = json.loads(out)

    assert payload["count"] == 1
    assert payload["total"] == 1
    record = payload["results"][0]
    for key in (
        "title",
        "abstract",
        "authors",
        "journal",
        "publication_date",
        "keywords",
        "doi",
        "data_source",
    ):
        assert key in record
    assert record["data_source"] == "CNKI"
    assert record["authors"] == ["张三", "李四"]
    assert record["doi"] == "10.3760/cma.j.123"


def test_default_five_year_range_applied_when_not_specified() -> None:
    captured: dict = {}

    def fetcher(req: CNKIRequest):
        captured["from"] = req.date_from
        captured["to"] = req.date_to
        return []

    today = dt.date(2024, 6, 15)
    server.search_cnki_impl("肿瘤", fetcher=fetcher, today=today)

    assert captured["to"] == "2024-06-15"
    assert captured["from"] == "2019-06-15"


def test_explicit_date_range_is_honored() -> None:
    captured: dict = {}

    def fetcher(req: CNKIRequest):
        captured["from"] = req.date_from
        captured["to"] = req.date_to
        return []

    server.search_cnki_impl(
        "高血压",
        date_from="2010-01-01",
        date_to="2012-12-31",
        fetcher=fetcher,
        today=dt.date(2024, 6, 15),
    )
    assert captured["from"] == "2010-01-01"
    assert captured["to"] == "2012-12-31"


def test_pagination_parameters_are_honored_and_clamped() -> None:
    captured: dict = {}

    def fetcher(req: CNKIRequest):
        captured["page"] = req.page
        captured["page_size"] = req.page_size
        return []

    out = server.search_cnki_impl("心血管", page=3, page_size=50, fetcher=fetcher)
    payload = json.loads(out)
    assert captured["page"] == 3
    assert captured["page_size"] == 50
    assert payload["page"] == 3
    assert payload["page_size"] == 50

    # Invalid values are clamped to safe defaults.
    server.reset()
    out = server.search_cnki_impl("心血管", page=0, page_size=9999, fetcher=fetcher)
    payload = json.loads(out)
    assert captured["page"] == 1
    assert captured["page_size"] == server.MAX_PAGE_SIZE
    assert payload["page"] == 1


def test_persistent_failure_raises_cnki_unavailable_after_retries() -> None:
    attempts: list[int] = []

    def always_fails(req: CNKIRequest):
        attempts.append(1)
        raise ConnectionError("network down")

    server.configure(max_retries=3, backoff_base=0.0)
    with pytest.raises(CNKIUnavailableError) as exc_info:
        server.search_cnki_impl("糖尿病", fetcher=always_fails)

    assert len(attempts) == 3
    assert "PubMed" in str(exc_info.value)


def test_missing_fetcher_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        server.search_cnki_impl("糖尿病")


def test_configured_fetcher_is_used_when_no_override() -> None:
    def fetcher(req: CNKIRequest):
        return [{"title": "configured"}]

    server.configure(fetcher=fetcher)
    payload = json.loads(server.search_cnki_impl("x"))
    assert payload["results"][0]["title"] == "configured"


def test_returned_payload_is_json_round_trippable() -> None:
    def fetcher(req: CNKIRequest):
        return {"total": 2, "records": _fake_records() + [{"title": "另一篇"}]}

    out = server.search_cnki_impl("糖尿病", fetcher=fetcher)
    payload = json.loads(out)
    # Re-serialize and re-parse to confirm a stable round trip.
    again = json.loads(json.dumps(payload, ensure_ascii=False))
    assert again == payload
    assert again["count"] == 2
    assert {"query", "page", "page_size", "total", "count", "results"} <= set(again)


def test_query_echo_includes_filters() -> None:
    def fetcher(req: CNKIRequest):
        return []

    out = server.search_cnki_impl(
        "糖尿病",
        author="张三",
        journal="中华医学杂志",
        fetcher=fetcher,
        today=dt.date(2024, 1, 1),
    )
    payload = json.loads(out)
    assert payload["query"]["author"] == "张三"
    assert payload["query"]["journal"] == "中华医学杂志"
    assert payload["query"]["keywords"] == "糖尿病"
