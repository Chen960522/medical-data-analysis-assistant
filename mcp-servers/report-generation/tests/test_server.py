"""Tests for the thin MCP tool implementation layer.

These exercise the ``*_impl`` functions directly (the ``@server.tool()`` wrappers
delegate to them). Importing :mod:`report_generation.server` must not require the
``mcp`` package, a database, or S3; the tests confirm the generate -> export
round trip works with an injected uploader (no boto3/native libs needed).
"""

from __future__ import annotations

import json

import pytest

from report_generation import server
from report_generation.models import DEFAULT_SECTIONS


@pytest.fixture(autouse=True)
def _reset_server_state():
    """Reset injectable server state before and after each test."""
    server.reset()
    yield
    server.reset()


def test_generate_report_returns_json_with_required_sections() -> None:
    out = server.generate_report_impl("a-1")
    payload = json.loads(out)
    assert "report_id" in payload
    keys = [s["key"] for s in payload["sections"]]
    for required in DEFAULT_SECTIONS:
        assert required in keys
    # analysis_id flows through into the report content.
    assert payload["analysis_id"] == "a-1"


def test_generate_report_uses_injected_loader() -> None:
    def loader(analysis_id: str) -> dict:
        return {
            "metadata": {"file_name": f"{analysis_id}.csv", "row_count": 42, "column_count": 5},
            "results": [{"result_type": "key_findings", "result_data": ["发现一"]}],
        }

    server.configure(analysis_loader=loader)
    payload = json.loads(server.generate_report_impl("study-9"))
    assert payload["metadata"]["file_name"] == "study-9.csv"
    assert payload["metadata"]["row_count"] == 42
    assert payload["metadata"]["column_count"] == 5


def test_generate_then_export_round_trip_with_injected_uploader() -> None:
    captured: dict = {}

    def fake_uploader(data: bytes, key: str, content_type: str) -> str:
        captured["data"] = data
        captured["key"] = key
        captured["content_type"] = content_type
        return f"https://example.test/{key}"

    server.configure(report_uploader=fake_uploader)

    # Use an injected loader so we do not depend on native export libs:
    # the docx exporter is pure-python (python-docx) and skipped if missing.
    docx = pytest.importorskip("docx")  # noqa: F841
    payload = json.loads(server.generate_report_impl("a-7"))
    report_id = payload["report_id"]

    out = json.loads(server.export_report_impl(report_id, format="docx"))
    assert out["report_id"] == report_id
    assert out["format"] == "docx"
    assert out["download_url"] == f"https://example.test/reports/{report_id}.docx"
    assert captured["key"] == f"reports/{report_id}.docx"
    assert isinstance(captured["data"], bytes) and len(captured["data"]) > 0


def test_export_unknown_report_id_raises() -> None:
    with pytest.raises(KeyError):
        server.export_report_impl("does-not-exist")


def test_export_unsupported_format_raises() -> None:
    payload = json.loads(server.generate_report_impl("a-2"))
    with pytest.raises(ValueError):
        server.export_report_impl(payload["report_id"], format="txt")


def test_export_without_storage_configured_raises() -> None:
    pytest.importorskip("docx")
    payload = json.loads(server.generate_report_impl("a-3"))
    # No uploader and no bucket configured -> explicit RuntimeError.
    with pytest.raises(RuntimeError):
        server.export_report_impl(payload["report_id"], format="docx")


def test_custom_sections_subset_still_complete_via_tool() -> None:
    payload = json.loads(server.generate_report_impl("a-4", sections=["recommendations"]))
    keys = [s["key"] for s in payload["sections"]]
    assert keys[0] == "recommendations"
    for required in DEFAULT_SECTIONS:
        assert required in keys
