"""Analysis request/response schemas.

Pydantic models for the Agent-driven analysis API (start, status, results,
charts, dimensions, history). Mirrors the response-model style in
``app/schemas/data.py`` (``model_config = {"from_attributes": True}``).

Requirements: 3.1-3.8, 6.1-6.5
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class StartAnalysisRequest(BaseModel):
    """Request body for starting an analysis."""

    file_id: uuid.UUID


class AnalysisSessionResponse(BaseModel):
    """Response schema for an analysis session record."""

    id: uuid.UUID
    file_id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisStatusResponse(BaseModel):
    """Response schema for analysis progress/status.

    ``stage`` is a human-readable label for the current analysis stage and
    ``progress`` is a 0-100 percentage, supporting the progress indicator
    described in Requirement 3.7.
    """

    id: uuid.UUID
    status: str
    stage: str
    progress: int


class AnalysisResultResponse(BaseModel):
    """Response schema for a single analysis result row."""

    id: uuid.UUID
    result_type: str
    result_data: dict[str, Any]

    model_config = {"from_attributes": True}


class ChartResponse(BaseModel):
    """Response schema for a generated chart row."""

    id: uuid.UUID
    chart_type: str
    title: str
    echarts_option: dict[str, Any]

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    """Response schema for a generated report."""

    id: uuid.UUID
    title: str
    content: dict[str, Any]

    model_config = {"from_attributes": True}


class DimensionResponse(BaseModel):
    """Response schema for an analysis dimension."""

    id: uuid.UUID
    name: str
    dimension_type: str
    config: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class StartAnalysisResponse(BaseModel):
    """Response schema for starting an analysis.

    Returns the created session together with the artifacts persisted from the
    Agent's first analysis pass (results, charts, optional report).
    """

    session: AnalysisSessionResponse
    results: list[AnalysisResultResponse]
    charts: list[ChartResponse]
    report: Optional[ReportResponse] = None


class AnalysisResultsResponse(BaseModel):
    """Response schema for the persisted analysis results of a session."""

    session: AnalysisSessionResponse
    results: list[AnalysisResultResponse]
    report: Optional[ReportResponse] = None


class ChartsResponse(BaseModel):
    """Response schema for the persisted charts of a session."""

    analysis_id: uuid.UUID
    charts: list[ChartResponse]
    total: int


class DimensionRequest(BaseModel):
    """Request body for adding an analysis dimension via natural language."""

    description: str
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class DimensionResultResponse(BaseModel):
    """Response schema after adding a dimension.

    Includes the created dimension plus any supplementary results/charts the
    Agent produced for it.
    """

    dimension: DimensionResponse
    results: list[AnalysisResultResponse]
    charts: list[ChartResponse]


class AnalysisHistoryResponse(BaseModel):
    """Response schema for analysis history (sorted by date descending)."""

    sessions: list[AnalysisSessionResponse]
    total: int
