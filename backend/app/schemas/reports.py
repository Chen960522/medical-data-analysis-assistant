"""Report request/response schemas.

Pydantic models for the Agent-driven report-generation API (generate a report
for an analysis, and download an exported report file). Mirrors the
response-model style in ``app/schemas/analysis.py``
(``model_config = {"from_attributes": True}``).

The structured report ``content`` (data summary, key findings, statistical
results, visualizations, recommendations + data-source metadata) is produced by
the self-developed report-generation MCP via the Agent and persisted verbatim;
the API additionally tracks which export formats (PDF / Word) are available for
download.

Requirements: 5.1-5.7
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class GenerateReportRequest(BaseModel):
    """Request body for generating a report from an analysis session.

    ``sections`` optionally restricts/orders the report sections (the five
    required sections are always present regardless). ``format`` is an optional
    hint forwarded to the Agent for the export format(s) to produce.
    """

    analysis_id: uuid.UUID
    sections: Optional[list[str]] = None
    format: Optional[str] = None


class ReportResponse(BaseModel):
    """Response schema for a generated report.

    Exposes the structured report ``content`` alongside boolean download
    availability flags (rather than raw S3 keys) so clients know which formats
    can be downloaded via the download endpoint (Requirement 5.5).
    """

    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    content: dict[str, Any]
    has_pdf: bool
    has_docx: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportDownloadResponse(BaseModel):
    """Response schema for a report download request.

    Returns a presigned URL the client can use to download the exported report
    file from S3, together with the resolved format.
    """

    download_url: str
    format: str
