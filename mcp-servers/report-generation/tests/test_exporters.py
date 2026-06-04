"""Tests for the export helpers (PDF/Word/S3).

The heavy / native dependencies are optional, so these tests use
``pytest.importorskip`` and are skipped cleanly when the libraries (or their
native deps, in WeasyPrint's case) are unavailable. The pure
``export_report_bytes`` format-dispatch logic and error paths are tested without
requiring any of those libraries.
"""

from __future__ import annotations

import pytest

from report_generation import build_report_content
from report_generation.exporters import EXPORT_FORMATS, export_report_bytes


def _report():
    return build_report_content(
        {
            "title": "导出测试报告",
            "metadata": {"file_name": "export.csv", "row_count": 5, "column_count": 2},
            "results": [{"result_type": "key_findings", "result_data": ["发现"]}],
            "charts": [
                {
                    "chart_id": "c1",
                    "title": "图一",
                    "chart_type": "bar",
                    "image_data_uri": "data:image/png;base64,AAAA",
                }
            ],
        }
    )


def test_export_format_registry_supports_pdf_and_docx() -> None:
    assert set(EXPORT_FORMATS) == {"pdf", "docx"}
    _, pdf_ct, pdf_ext = EXPORT_FORMATS["pdf"]
    _, docx_ct, docx_ext = EXPORT_FORMATS["docx"]
    assert pdf_ext == "pdf" and pdf_ct == "application/pdf"
    assert docx_ext == "docx"
    assert "wordprocessingml" in docx_ct


def test_export_report_bytes_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        export_report_bytes(_report(), fmt="rtf")


def test_export_report_bytes_normalizes_format_casing() -> None:
    # ".PDF" should normalize; but if weasyprint native libs are missing we skip.
    pytest.importorskip("weasyprint")
    data, content_type, ext = export_report_bytes(_report(), fmt=".PDF")
    assert ext == "pdf"
    assert content_type == "application/pdf"
    assert isinstance(data, bytes) and data[:4] == b"%PDF"


def test_export_docx_produces_nonempty_bytes() -> None:
    pytest.importorskip("docx")
    from report_generation.exporters import export_docx

    data = export_docx(_report(), include_charts=True)
    assert isinstance(data, bytes) and len(data) > 0
    # .docx files are zip archives -> start with PK signature.
    assert data[:2] == b"PK"


def test_export_pdf_produces_pdf_bytes() -> None:
    pytest.importorskip("weasyprint")
    from report_generation.exporters import export_pdf

    data = export_pdf(_report(), include_charts=True)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_upload_to_s3_uses_boto3_when_available(monkeypatch) -> None:
    boto3 = pytest.importorskip("boto3")
    from report_generation.exporters import upload_to_s3

    calls: dict = {}

    class _FakeClient:
        def put_object(self, **kwargs):
            calls["put"] = kwargs

        def generate_presigned_url(self, op, Params, ExpiresIn):  # noqa: N803 (boto3 API casing)
            calls["presign"] = (op, Params, ExpiresIn)
            return f"https://s3.example/{Params['Key']}"

    monkeypatch.setattr(boto3, "client", lambda service: _FakeClient())

    url = upload_to_s3(b"bytes", "my-bucket", "reports/r.pdf", content_type="application/pdf")
    assert url == "https://s3.example/reports/r.pdf"
    assert calls["put"]["Bucket"] == "my-bucket"
    assert calls["put"]["Key"] == "reports/r.pdf"
    assert calls["put"]["ContentType"] == "application/pdf"
