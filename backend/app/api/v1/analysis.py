"""Agent-driven data analysis API routes.

Implements analysis lifecycle endpoints backed by the 「医析」 Agent running on
Bedrock AgentCore: starting an analysis, querying progress, fetching results and
charts, managing analysis dimensions, listing history, and deleting records.

All endpoints enforce per-user data isolation (Requirements 6.x, 8.x) by scoping
every query to the authenticated user via the access-control helpers.

The :class:`AgentCoreClient` is provided through the ``get_agentcore_client``
FastAPI dependency so tests can override it (``app.dependency_overrides``) with a
fake that returns canned ``AgentResponse`` objects, avoiding real AWS calls.

Requirements: 3.1-3.8, 6.1-6.5
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...middleware.access_control import get_resource_or_deny
from ...middleware.auth import get_current_user
from ...models.analysis import AnalysisDimension, AnalysisResult, AnalysisSession, Chart
from ...models.data import DataFile
from ...models.report import Report
from ...models.user import User
from ...schemas.analysis import (
    AnalysisHistoryResponse,
    AnalysisResultResponse,
    AnalysisResultsResponse,
    AnalysisSessionResponse,
    AnalysisStatusResponse,
    ChartResponse,
    ChartsResponse,
    DimensionRequest,
    DimensionResponse,
    DimensionResultResponse,
    ReportResponse,
    StartAnalysisRequest,
    StartAnalysisResponse,
)
from ...services.agentcore_client import AgentCoreClient, AgentResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Module-level AgentCore client. Provided via a dependency so tests can override
# it with a fake invoker (see get_agentcore_client).
_agentcore_client = AgentCoreClient()


def get_agentcore_client() -> AgentCoreClient:
    """FastAPI dependency returning the shared AgentCore client.

    Tests override this via ``app.dependency_overrides[get_agentcore_client]``
    to inject a fake that returns canned :class:`AgentResponse` objects.
    """
    return _agentcore_client


# Maps a session status to a (stage label, progress percentage) pair for the
# progress indicator (Requirement 3.7).
_STATUS_STAGE: dict[str, tuple[str, int]] = {
    "pending": ("排队中", 0),
    "running": ("分析进行中", 50),
    "completed": ("分析完成", 100),
    "failed": ("分析失败", 0),
}


def _now() -> datetime:
    """Return a timezone-aware current timestamp."""
    return datetime.now(timezone.utc)


def _derive_chart_type(option: dict) -> str:
    """Derive a chart type label from an ECharts option dict."""
    series = option.get("series")
    if isinstance(series, list) and series:
        first = series[0]
        if isinstance(first, dict) and first.get("type"):
            return str(first["type"])
    if isinstance(series, dict) and series.get("type"):
        return str(series["type"])
    return "unknown"


def _derive_chart_title(option: dict) -> str:
    """Derive a chart title from an ECharts option dict."""
    title = option.get("title")
    if isinstance(title, dict):
        text = title.get("text")
        if text:
            return str(text)
    elif isinstance(title, str) and title:
        return title
    return "图表"


def _persist_charts(db: Session, session_id: uuid_mod.UUID, charts: list[dict]) -> list[Chart]:
    """Persist Agent-returned ECharts options as Chart rows."""
    created: list[Chart] = []
    for item in charts:
        if not isinstance(item, dict):
            continue
        # Support both bare option dicts and {chart_type, title, option} wrappers.
        is_wrapper = isinstance(item.get("option"), dict)
        option = item["option"] if is_wrapper else item
        chart_type = str(item.get("chart_type") or _derive_chart_type(option))
        # A wrapper may carry an explicit string title; otherwise derive from the
        # ECharts option (whose own ``title`` is a {"text": ...} object).
        wrapper_title = item.get("title") if is_wrapper else None
        title = str(wrapper_title) if isinstance(wrapper_title, str) and wrapper_title else _derive_chart_title(option)
        chart = Chart(
            session_id=session_id,
            chart_type=chart_type,
            title=title,
            echarts_option=option,
        )
        db.add(chart)
        created.append(chart)
    return created


def _persist_results(
    db: Session, session_id: uuid_mod.UUID, results: list[dict]
) -> list[AnalysisResult]:
    """Persist Agent-returned analysis results as AnalysisResult rows."""
    created: list[AnalysisResult] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        result_type = str(item.get("result_type") or "analysis")
        result_data = item.get("result_data")
        if not isinstance(result_data, dict):
            # Fall back to storing the whole item (minus the type key) as data.
            result_data = {k: v for k, v in item.items() if k != "result_type"}
        result = AnalysisResult(
            session_id=session_id,
            result_type=result_type,
            result_data=result_data,
        )
        db.add(result)
        created.append(result)
    return created


def _persist_report(
    db: Session, session_id: uuid_mod.UUID, user_id: uuid_mod.UUID, report: dict | None
) -> Report | None:
    """Persist an Agent-returned report as a Report row, if present."""
    if not isinstance(report, dict) or not report:
        return None
    title = str(report.get("title") or "分析报告")
    row = Report(
        session_id=session_id,
        user_id=user_id,
        title=title,
        content=report,
    )
    db.add(row)
    return row


async def _invoke_agent(
    client: AgentCoreClient, prompt: str, user_id: uuid_mod.UUID, analysis_context: dict[str, Any]
) -> AgentResponse:
    """Invoke the Agent, translating failures into a 502 error."""
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


def _get_session_or_deny(
    db: Session, analysis_id: uuid_mod.UUID, user_id: uuid_mod.UUID
) -> AnalysisSession:
    """Load an analysis session enforcing ownership (404/403)."""
    return get_resource_or_deny(
        db, AnalysisSession, analysis_id, user_id, "analysis session"
    )


def _report_response_for_session(
    db: Session, session_id: uuid_mod.UUID
) -> ReportResponse | None:
    """Return the latest report for a session as a response model, if any."""
    report = db.execute(
        select(Report)
        .where(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
    ).scalars().first()
    return ReportResponse.model_validate(report) if report is not None else None


@router.post("/start", response_model=StartAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def start_analysis(
    body: StartAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> StartAnalysisResponse:
    """Start an Agent-driven analysis for an uploaded data file.

    Validates the file belongs to the user, creates an AnalysisSession, invokes
    the Agent to perform multidimensional analysis, and persists the returned
    results, charts, and report.
    Requirements: 3.1-3.7, 6.1
    """
    # Validate file ownership (404 if missing, 403 if another user's).
    data_file = get_resource_or_deny(db, DataFile, body.file_id, current_user.id, "data file")

    # Create the session in a running state.
    session = AnalysisSession(
        user_id=current_user.id,
        file_id=data_file.id,
        status="running",
        started_at=_now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    prompt = (
        f"请对数据文件「{data_file.original_filename}」(file_id={data_file.id}) 进行多维度医学数据分析，"
        "包括描述性统计、数值变量相关性、异常值检测、时间序列趋势分析（如有日期列）以及按分类变量分组比较，"
        "并生成相应的可视化图表和结构化分析报告。"
    )
    analysis_context = {
        "file_id": str(data_file.id),
        "filename": data_file.original_filename,
        "row_count": data_file.row_count,
        "column_count": data_file.column_count,
    }

    try:
        agent_response = await _invoke_agent(client, prompt, current_user.id, analysis_context)
    except HTTPException:
        session.status = "failed"
        db.commit()
        raise

    # Persist artifacts returned by the Agent.
    results = _persist_results(db, session.id, agent_response.analysis_results)
    charts = _persist_charts(db, session.id, agent_response.charts)
    report = _persist_report(db, session.id, current_user.id, agent_response.report)

    session.status = "completed"
    session.completed_at = _now()
    db.commit()
    db.refresh(session)
    for row in results + charts:
        db.refresh(row)
    if report is not None:
        db.refresh(report)

    return StartAnalysisResponse(
        session=AnalysisSessionResponse.model_validate(session),
        results=[AnalysisResultResponse.model_validate(r) for r in results],
        charts=[ChartResponse.model_validate(c) for c in charts],
        report=ReportResponse.model_validate(report) if report is not None else None,
    )


@router.get("/history", response_model=AnalysisHistoryResponse)
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisHistoryResponse:
    """Get the user's analysis history sorted by date descending.

    Requirements: 6.2, 8.19
    """
    stmt = (
        select(AnalysisSession)
        .where(AnalysisSession.user_id == current_user.id)
        .order_by(AnalysisSession.created_at.desc())
    )
    sessions = db.execute(stmt).scalars().all()
    return AnalysisHistoryResponse(
        sessions=[AnalysisSessionResponse.model_validate(s) for s in sessions],
        total=len(sessions),
    )


@router.get("/{analysis_id}/status", response_model=AnalysisStatusResponse)
def get_status(
    analysis_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Query analysis progress for a session.

    Requirements: 3.7
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)
    stage, progress = _STATUS_STAGE.get(session.status, (session.status, 0))
    return AnalysisStatusResponse(
        id=session.id,
        status=session.status,
        stage=stage,
        progress=progress,
    )


@router.get("/{analysis_id}/results", response_model=AnalysisResultsResponse)
def get_results(
    analysis_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResultsResponse:
    """Get the persisted analysis results for a session.

    Requirements: 3.1-3.5, 6.3
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)

    results = db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.session_id == session.id)
        .order_by(AnalysisResult.created_at.asc())
    ).scalars().all()

    return AnalysisResultsResponse(
        session=AnalysisSessionResponse.model_validate(session),
        results=[AnalysisResultResponse.model_validate(r) for r in results],
        report=_report_response_for_session(db, session.id),
    )


@router.get("/{analysis_id}/charts", response_model=ChartsResponse)
def get_charts(
    analysis_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChartsResponse:
    """Get the persisted charts for a session.

    Requirements: 4.1-4.6, 6.3
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)

    charts = db.execute(
        select(Chart)
        .where(Chart.session_id == session.id)
        .order_by(Chart.created_at.asc())
    ).scalars().all()

    return ChartsResponse(
        analysis_id=session.id,
        charts=[ChartResponse.model_validate(c) for c in charts],
        total=len(charts),
    )


@router.post(
    "/{analysis_id}/dimensions",
    response_model=DimensionResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dimension(
    analysis_id: uuid_mod.UUID,
    body: DimensionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> DimensionResultResponse:
    """Add a user-requested analysis dimension via the Agent.

    Creates a user dimension, invokes the Agent with the natural-language
    description to produce supplementary results/charts, persists them, and
    returns the dimension plus the new artifacts.
    Requirements: 3.8, 9.6, 9.7, 9.19, 9.20
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)

    dimension = AnalysisDimension(
        session_id=session.id,
        name=body.name or body.description[:255],
        dimension_type="user",
        config=body.config,
    )
    db.add(dimension)
    db.commit()
    db.refresh(dimension)

    prompt = (
        f"在分析会话 (analysis_id={session.id}) 的现有数据基础上，"
        f"新增以下分析维度并生成补充分析结果和图表：{body.description}"
    )
    analysis_context = {
        "analysis_id": str(session.id),
        "dimension_id": str(dimension.id),
        "dimension_name": dimension.name,
    }

    agent_response = await _invoke_agent(client, prompt, current_user.id, analysis_context)

    results = _persist_results(db, session.id, agent_response.analysis_results)
    charts = _persist_charts(db, session.id, agent_response.charts)
    db.commit()
    db.refresh(dimension)
    for row in results + charts:
        db.refresh(row)

    return DimensionResultResponse(
        dimension=DimensionResponse.model_validate(dimension),
        results=[AnalysisResultResponse.model_validate(r) for r in results],
        charts=[ChartResponse.model_validate(c) for c in charts],
    )


@router.delete(
    "/{analysis_id}/dimensions/{dim_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_dimension(
    analysis_id: uuid_mod.UUID,
    dim_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove an analysis dimension from a session.

    Requirements: 9.20, 9.21
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)

    dimension = db.execute(
        select(AnalysisDimension).where(
            AnalysisDimension.id == dim_id,
            AnalysisDimension.session_id == session.id,
        )
    ).scalar_one_or_none()

    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dimension not found",
        )

    db.delete(dimension)
    db.commit()


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete an analysis record and its associated data.

    The AnalysisSession model cascades deletes to results, dimensions, charts,
    and reports (``cascade="all, delete-orphan"``).
    Requirements: 6.4, 7.5, 8.20
    """
    session = _get_session_or_deny(db, analysis_id, current_user.id)
    db.delete(session)
    db.commit()
