"""MCP server exposing report-generation tools.

This module is a thin layer over the pure report-content logic in
:mod:`report_generation.builder` / :mod:`report_generation.templates` and the
lazy export helpers in :mod:`report_generation.exporters`.

Design goals:

* Importing this module MUST NOT require the ``mcp`` package, a database, S3, or
  the heavy native export libraries. The MCP runtime (``FastMCP``) is imported
  lazily inside :func:`create_server`; the export libraries are imported lazily
  inside the exporters.
* The actual tool logic lives in plain ``*_impl`` functions so it can be unit
  tested directly. The ``@server.tool()`` wrappers registered in
  :func:`create_server` simply delegate to these.
* Data loading (analysis results) and persistence (report store, S3 bucket) are
  injected via :func:`configure`, so the tools never hard-depend on a concrete
  database/S3 client.

Tools:
    ``generate_report(analysis_id, sections=None) -> str``
        Returns JSON report content with section text and inline chart refs.
    ``export_report(report_id, format="pdf", include_charts=True) -> str``
        Renders the stored report to PDF/Word, uploads to S3, returns a URL.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from .builder import build_report_content
from .exporters import export_report_bytes, upload_to_s3
from .models import ReportContent

SERVER_NAME = "report-generation"

# Type aliases for the injectable integration hooks.
AnalysisLoader = Callable[[str], dict[str, Any] | None]
ReportUploader = Callable[[bytes, str, str], str]

# --- Module-level, injectable configuration -------------------------------
# These are intentionally simple so the tools remain pure/testable. The backend
# wires real implementations in via configure(); the defaults degrade safely.

_analysis_loader: AnalysisLoader | None = None
_report_uploader: ReportUploader | None = None
_report_bucket: str | None = None
_report_key_prefix: str = "reports"

# In-memory store mapping report_id -> ReportContent. The backend may replace
# this by supplying its own loader for export, but the in-memory store keeps the
# generate -> export round trip working out of the box (and in tests).
_report_store: dict[str, ReportContent] = {}


def configure(
    *,
    analysis_loader: AnalysisLoader | None = None,
    report_uploader: ReportUploader | None = None,
    report_bucket: str | None = None,
    report_key_prefix: str | None = None,
) -> None:
    """Wire integration hooks used by the tool implementations.

    Args:
        analysis_loader: Callable that maps an ``analysis_id`` to a dict of
            analysis data (as consumed by :func:`build_report_content`). If not
            configured, :func:`generate_report_impl` builds from the minimal
            data it is given (the builder is robust to empty/partial input).
        report_uploader: Callable ``(data, key, content_type) -> url`` used to
            persist exported files. Defaults to uploading to ``report_bucket``
            via :func:`report_generation.exporters.upload_to_s3`.
        report_bucket: Default S3 bucket name for exported reports.
        report_key_prefix: Key prefix (folder) for exported report objects.
    """
    global _analysis_loader, _report_uploader, _report_bucket, _report_key_prefix
    if analysis_loader is not None:
        _analysis_loader = analysis_loader
    if report_uploader is not None:
        _report_uploader = report_uploader
    if report_bucket is not None:
        _report_bucket = report_bucket
    if report_key_prefix is not None:
        _report_key_prefix = report_key_prefix


def reset() -> None:
    """Reset injectable state and the in-memory report store (test helper)."""
    global _analysis_loader, _report_uploader, _report_bucket, _report_key_prefix
    _analysis_loader = None
    _report_uploader = None
    _report_bucket = None
    _report_key_prefix = "reports"
    _report_store.clear()


# --- Tool implementations (pure-ish, directly unit-testable) ---------------


def generate_report_impl(analysis_id: str, sections: list[str] | None = None) -> str:
    """Build structured report content for an analysis and store it.

    Loads analysis data via the configured loader (falling back to a minimal
    payload), builds a :class:`ReportContent` with the five required sections,
    stores it in the in-memory report store, and returns its JSON serialization
    (including a generated ``report_id``).

    Args:
        analysis_id: The analysis session identifier.
        sections: Optional subset/ordering of section keys (required sections
            are always present regardless).

    Returns:
        A JSON string of the report content plus ``report_id``.
    """
    analysis_data = _load_analysis_data(analysis_id)
    report = build_report_content(analysis_data, sections=sections)

    report_id = str(uuid.uuid4())
    _report_store[report_id] = report

    payload = report.to_dict()
    payload["report_id"] = report_id
    return json.dumps(payload, ensure_ascii=False)


def export_report_impl(report_id: str, format: str = "pdf", include_charts: bool = True) -> str:
    """Export a previously generated report and return a download URL.

    Args:
        report_id: Identifier returned by :func:`generate_report_impl`.
        format: Output format, ``"pdf"`` or ``"docx"``.
        include_charts: Whether to embed inline charts (Requirement 5.4).

    Returns:
        A JSON string ``{"report_id", "format", "download_url"}``.

    Raises:
        KeyError: If ``report_id`` is unknown.
        ValueError: If ``format`` is unsupported.
    """
    report = _report_store.get(report_id)
    if report is None:
        raise KeyError(f"Unknown report_id: {report_id!r}. Call generate_report first.")

    data, content_type, extension = export_report_bytes(report, fmt=format, include_charts=include_charts)
    key = f"{_report_key_prefix.rstrip('/')}/{report_id}.{extension}"
    download_url = _upload(data, key, content_type)

    return json.dumps(
        {"report_id": report_id, "format": extension, "download_url": download_url},
        ensure_ascii=False,
    )


# --- Internal helpers ------------------------------------------------------


def _load_analysis_data(analysis_id: str) -> dict[str, Any]:
    """Load analysis data via the configured loader, with a safe fallback."""
    if _analysis_loader is not None:
        loaded = _analysis_loader(analysis_id)
        if isinstance(loaded, dict):
            data = dict(loaded)
            data.setdefault("analysis_id", analysis_id)
            return data
    return {"analysis_id": analysis_id}


def _upload(data: bytes, key: str, content_type: str) -> str:
    """Persist exported bytes and return a download URL."""
    if _report_uploader is not None:
        return _report_uploader(data, key, content_type)
    if _report_bucket:
        return upload_to_s3(data, _report_bucket, key, content_type=content_type)
    raise RuntimeError(
        "No report storage configured. Call configure(report_bucket=...) or "
        "configure(report_uploader=...) before exporting a report."
    )


# --- MCP server factory ----------------------------------------------------


def create_server():
    """Create and configure the FastMCP server instance.

    ``mcp`` is imported lazily here so that importing this module (and running
    the pure unit tests) does not require the MCP runtime to be installed.

    Returns:
        A configured ``FastMCP`` server exposing ``generate_report`` and
        ``export_report`` tools.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'mcp' package is required to run the report-generation server. "
            "Install it with 'pip install mcp'."
        ) from exc

    server = FastMCP(SERVER_NAME)

    @server.tool()
    async def generate_report(analysis_id: str, sections: list[str] | None = None) -> str:
        """根据分析结果生成结构化报告。

        Args:
            analysis_id: 分析会话 ID。
            sections: 可选，指定报告包含的章节列表（五个必备章节始终存在）。

        Returns:
            JSON 格式的报告内容，包含各章节文本和内嵌图表引用，以及 report_id。
        """
        return generate_report_impl(analysis_id, sections=sections)

    @server.tool()
    async def export_report(report_id: str, format: str = "pdf", include_charts: bool = True) -> str:
        """将报告导出为 PDF 或 Word 文件。

        Args:
            report_id: 报告 ID（由 generate_report 返回）。
            format: 导出格式 (pdf/docx)。
            include_charts: 是否包含内嵌图表。

        Returns:
            导出文件的 S3 下载链接（JSON）。
        """
        return export_report_impl(report_id, format=format, include_charts=include_charts)

    return server
