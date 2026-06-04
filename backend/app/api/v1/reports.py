"""Agent-driven report generation and download API routes.

Implements the report endpoints backed by the 「医析」 Agent running on Bedrock
AgentCore together with the self-developed report-generation MCP server:

* ``POST /generate`` — instruct the Agent to generate a structured
  Analysis_Report for an analysis session (data summary, key findings,
  statistical results, visualizations, recommendations + data-source metadata),
  persist it as a :class:`Report` row, and capture any exported PDF/Word S3
  keys the Agent returns.
* ``GET /{report_id}/download`` — return a presigned S3 URL for downloading the
  exported report in the requested format (``pdf`` default or ``docx``).

All endpoints enforce per-user data isolation (Requirements 8.x) by scoping
every query to the authenticated user via the access-control helpers: the
``analysis_id`` AnalysisSession on generate, and the Report on download.

The :class:`AgentCoreClient` is provided through the shared
``get_agentcore_client`` dependency (imported from :mod:`app.api.v1.analysis`)
so tests can override it (``app.dependency_overrides``) with a fake that returns
canned ``AgentResponse`` objects, avoiding real AWS calls. S3 access goes
through the module-level :mod:`app.services.s3_client` functions so tests can
monkeypatch them.

Requirements: 5.1-5.7
"""

import uuid as uuid_mod
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...middleware.access_control import get_resource_or_deny
from ...middleware.auth import get_current_user
from ...models.analysis import AnalysisSession
from ...models.report import Report
from ...models.user import User
from ...schemas.reports import (
    GenerateReportRequest,
    ReportDownloadResponse,
    ReportResponse,
)
from ...services import s3_client
from ...services.agentcore_client import AgentCoreClient, AgentResponse
from .analysis import get_agentcore_client

router = APIRouter(prefix="/reports", tags=["reports"])

# Supported export formats mapped to (Report S3-key attribute, file extension).
_FORMAT_KEY_ATTR: dict[str, str] = {
    "pdf": "s3_key_pdf",
    "docx": "s3_key_docx",
}


def _report_response(report: Report) -> ReportResponse:
    """Build a :class:`ReportResponse` from a Report row.

    Derives the ``has_pdf``/``has_docx`` download-availability flags from the
    presence of the corresponding S3 keys rather than exposing the raw keys.
    """
    return ReportResponse(
        id=report.id,
        session_id=report.session_id,
        title=report.title,
        content=report.content,
        has_pdf=report.s3_key_pdf is not None,
        has_docx=report.s3_key_docx is not None,
        created_at=report.created_at,
    )


def _extract_s3_keys(report_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract exported PDF/Word S3 keys from an Agent report payload.

    The report-generation MCP's ``export_report`` tool uploads files to S3 and
    returns download metadata. The Agent may surface those under a variety of
    shapes; this helper accepts the common ones:

    * ``report["s3_key_pdf"]`` / ``report["s3_key_docx"]`` (explicit keys)
    * ``report["exports"]`` as a list of ``{"format": "pdf"|"docx",
      "s3_key": ...}`` entries
    * ``report["exports"]`` as a mapping ``{"pdf": {"s3_key": ...}, ...}``

    Returns a ``(s3_key_pdf, s3_key_docx)`` tuple with ``None`` for any format
    that was not exported.
    """
    s3_key_pdf = report_payload.get("s3_key_pdf")
    s3_key_docx = report_payload.get("s3_key_docx")

    exports = report_payload.get("exports")
    if isinstance(exports, list):
        for entry in exports:
            if not isinstance(entry, dict):
                continue
            fmt = str(entry.get("format") or "").lower()
            key = entry.get("s3_key")
            if fmt == "pdf" and s3_key_pdf is None:
                s3_key_pdf = key
            elif fmt == "docx" and s3_key_docx is None:
                s3_key_docx = key
    elif isinstance(exports, dict):
        if s3_key_pdf is None and isinstance(exports.get("pdf"), dict):
            s3_key_pdf = exports["pdf"].get("s3_key")
        if s3_key_docx is None and isinstance(exports.get("docx"), dict):
            s3_key_docx = exports["docx"].get("s3_key")

    pdf = str(s3_key_pdf) if isinstance(s3_key_pdf, str) and s3_key_pdf else None
    docx = str(s3_key_docx) if isinstance(s3_key_docx, str) and s3_key_docx else None
    return pdf, docx


async def _invoke_agent(
    client: AgentCoreClient,
    prompt: str,
    user_id: uuid_mod.UUID,
    analysis_context: dict[str, Any],
) -> AgentResponse:
    """Invoke the Agent, translating failures into a 502 error.

    Mirrors the failure handling in ``analysis.py``/``chat.py``: any exception
    from the AgentCore call is surfaced as an HTTP 502 Bad Gateway.
    """
    payload = {
        "prompt": prompt,
        "user_id": str(user_id),
        "analysis_context": analysis_context,
    }
    try:
        return await client.invoke_agent(payload)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent invocation failed: {exc}",
        ) from exc


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    body: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> ReportResponse:
    """Generate a structured analysis report for an analysis session.

    Validates the analysis session belongs to the user, invokes the Agent (which
    drives the report-generation MCP to build the structured content and export
    PDF/Word files to S3), persists a :class:`Report` row with the returned
    content and any exported S3 keys, and returns it.

    Persisting the structured content satisfies Requirements 5.1-5.4 and 5.7;
    the export S3 keys back the download endpoint (Requirement 5.5).
    Requirements: 5.1-5.7
    """
    # Validate analysis ownership (404 if missing, 403 if another user's).
    session = get_resource_or_deny(
        db, AnalysisSession, body.analysis_id, current_user.id, "analysis session"
    )

    section_hint = (
        f"，报告章节包括：{', '.join(body.sections)}" if body.sections else ""
    )
    format_hint = f"，并导出为 {body.format} 格式" if body.format else "，并导出为 PDF 和 Word 格式"
    prompt = (
        f"请基于分析会话 (analysis_id={session.id}) 的分析结果生成结构化医学分析报告，"
        "包含数据摘要、关键发现、统计分析结果、可视化图表和建议五个章节，"
        f"并附带数据来源元数据（文件名、上传时间、行数、列数）{section_hint}{format_hint}。"
    )
    analysis_context: dict[str, Any] = {
        "analysis_id": str(session.id),
        "sections": body.sections,
        "format": body.format,
    }

    agent_response = await _invoke_agent(client, prompt, current_user.id, analysis_context)

    # Persist the structured report content. Fall back to a minimal structured
    # dict if the Agent did not return a report payload.
    report_payload = agent_response.report if isinstance(agent_response.report, dict) else {}
    content = report_payload or {
        "title": "分析报告",
        "analysis_id": str(session.id),
        "sections": [],
    }
    title = str(content.get("title") or "分析报告")
    s3_key_pdf, s3_key_docx = _extract_s3_keys(report_payload)

    report = Report(
        session_id=session.id,
        user_id=current_user.id,
        title=title,
        content=content,
        s3_key_pdf=s3_key_pdf,
        s3_key_docx=s3_key_docx,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return _report_response(report)


@router.get("/{report_id}/download", response_model=ReportDownloadResponse)
def download_report(
    report_id: uuid_mod.UUID,
    format: str = Query("pdf", description="报告下载格式：pdf 或 docx"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDownloadResponse:
    """Return a presigned S3 URL for downloading an exported report file.

    The report must belong to the authenticated user (404 if missing, 403 if
    another user's). The requested ``format`` must be a supported export format
    (``pdf`` or ``docx``) and must have been exported (its S3 key present),
    otherwise a 404 is returned. The presigned URL is generated via the
    ``s3_client`` module so tests can monkeypatch it.
    Requirements: 5.5, 8.20
    """
    normalized = format.lower()
    key_attr = _FORMAT_KEY_ATTR.get(normalized)
    if key_attr is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{format}'. Supported formats: pdf, docx.",
        )

    report = get_resource_or_deny(db, Report, report_id, current_user.id, "report")

    s3_key = getattr(report, key_attr)
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report is not available for download in '{normalized}' format.",
        )

    download_url = s3_client.get_presigned_url(s3_key)
    return ReportDownloadResponse(download_url=download_url, format=normalized)
