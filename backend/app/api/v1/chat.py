"""Conversational analysis API routes.

Implements the chat ("对话式分析交互") endpoints backed by the 「医析」 Agent
running on Bedrock AgentCore: creating a conversation session (optionally linked
to an analysis), sending a natural-language message and returning the Agent's
analysis results/charts inline, fetching conversation history, and fetching the
conversation context (previously executed analyses, active dimensions, generated
charts).

All endpoints enforce per-user data isolation (Requirements 8.x) by scoping
every query to the authenticated user via the access-control helpers.

The :class:`AgentCoreClient` is provided through the shared ``get_agentcore_client``
dependency (imported from :mod:`app.api.v1.analysis`) so tests can override it
(``app.dependency_overrides``) with a fake that returns canned ``AgentResponse``
objects, avoiding real AWS calls.

Requirements: 9.1-9.22
"""

import uuid as uuid_mod
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...middleware.access_control import get_resource_or_deny
from ...middleware.auth import get_current_user
from ...models.analysis import AnalysisDimension, AnalysisResult, AnalysisSession, Chart
from ...models.chat import ChatMessage, ChatSession
from ...models.user import User
from ...schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    ContextChartResponse,
    ContextDimensionResponse,
    ContextResultResponse,
    ConversationContextResponse,
    CreateChatSessionRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from ...services.agentcore_client import AgentCoreClient, AgentResponse
from .analysis import _persist_charts, _persist_results, get_agentcore_client

router = APIRouter(prefix="/chat", tags=["chat"])

# Maximum number of conversation turns per session (Requirement 9.17). A turn is
# one User message together with its assistant reply.
MAX_TURNS = 50


def _get_chat_session_or_deny(
    db: Session, session_id: uuid_mod.UUID, user_id: uuid_mod.UUID
) -> ChatSession:
    """Load a chat session enforcing ownership (404 missing / 403 cross-user)."""
    return get_resource_or_deny(db, ChatSession, session_id, user_id, "chat session")


def _linked_analysis_artifacts(
    db: Session, analysis_session_id: uuid_mod.UUID | None
) -> tuple[list[AnalysisResult], list[AnalysisDimension], list[Chart]]:
    """Load the results, dimensions, and charts of a linked analysis session.

    Returns empty lists when no analysis is linked (``analysis_session_id`` is
    ``None``), supporting conversations that are not tied to an analysis.
    """
    if analysis_session_id is None:
        return [], [], []

    results = db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.session_id == analysis_session_id)
        .order_by(AnalysisResult.created_at.asc())
    ).scalars().all()
    dimensions = db.execute(
        select(AnalysisDimension)
        .where(AnalysisDimension.session_id == analysis_session_id)
        .order_by(AnalysisDimension.created_at.asc())
    ).scalars().all()
    charts = db.execute(
        select(Chart)
        .where(Chart.session_id == analysis_session_id)
        .order_by(Chart.created_at.asc())
    ).scalars().all()
    return list(results), list(dimensions), list(charts)


def _build_analysis_context(db: Session, chat_session: ChatSession) -> dict[str, Any]:
    """Assemble the Conversation_Context payload passed to the Agent.

    Combines the prior conversation messages with the linked analysis session's
    executed results, active dimensions, and generated charts so the Agent can
    resolve references to earlier analyses (Requirements 9.14, 9.15, 9.16).
    """
    prior_messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()

    context: dict[str, Any] = {
        "chat_session_id": str(chat_session.id),
        "turn_count": chat_session.turn_count,
        "history": [{"role": m.role, "content": m.content} for m in prior_messages],
    }

    if chat_session.analysis_session_id is not None:
        results, dimensions, charts = _linked_analysis_artifacts(
            db, chat_session.analysis_session_id
        )
        context["analysis_session_id"] = str(chat_session.analysis_session_id)
        context["executed_analyses"] = [
            {"result_type": r.result_type, "result_data": r.result_data} for r in results
        ]
        context["active_dimensions"] = [
            {"name": d.name, "dimension_type": d.dimension_type} for d in dimensions
        ]
        context["generated_charts"] = [
            {"chart_type": c.chart_type, "title": c.title} for c in charts
        ]

    return context


async def _invoke_agent(
    client: AgentCoreClient,
    prompt: str,
    user_id: uuid_mod.UUID,
    session_id: uuid_mod.UUID,
    analysis_context: dict[str, Any],
) -> AgentResponse:
    """Invoke the Agent for a conversation turn, surfacing failures as 502.

    Passes the chat ``session_id`` to AgentCore for conversational continuity so
    the Agent resumes the same session across turns.
    """
    payload = {
        "prompt": prompt,
        "user_id": str(user_id),
        "analysis_context": analysis_context,
    }
    try:
        return await client.invoke_agent(payload, session_id=str(session_id))
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent invocation failed: {exc}",
        ) from exc


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: CreateChatSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    """Create a conversation session, optionally linked to an analysis.

    When ``analysis_session_id`` is provided it must belong to the user (404 if
    missing, 403 if another user's), establishing the analysis as the source of
    the conversation context.
    Requirements: 9.1, 9.4, 9.14
    """
    analysis_session_id = None
    if body.analysis_session_id is not None:
        analysis = get_resource_or_deny(
            db, AnalysisSession, body.analysis_session_id, current_user.id, "analysis session"
        )
        analysis_session_id = analysis.id

    session = ChatSession(
        user_id=current_user.id,
        analysis_session_id=analysis_session_id,
        turn_count=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return ChatSessionResponse.model_validate(session)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: uuid_mod.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> SendMessageResponse:
    """Send a message to the Agent and return its analysis results inline.

    Enforces the 50-turn limit BEFORE invoking the Agent, persists the user and
    assistant messages, builds the conversation context, and (when linked to an
    analysis) persists new charts/results onto that analysis so they appear on
    the dashboard.
    Requirements: 9.2, 9.5-9.13, 9.14-9.16, 9.17, 9.18
    """
    session = _get_chat_session_or_deny(db, session_id, current_user.id)

    # Enforce the conversation turn limit before doing any work (Req 9.17, 9.18).
    if session.turn_count >= MAX_TURNS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"对话已达到最大轮次限制（{MAX_TURNS} 轮）。"
                "请创建新的对话会话以继续，已生成的分析结果将被保留。"
            ),
        )

    # Build the conversation context from prior messages + linked analysis BEFORE
    # persisting the new user message (the new message is the prompt).
    analysis_context = _build_analysis_context(db, session)

    # Persist the user's message.
    user_message = ChatMessage(session_id=session.id, role="user", content=body.message)
    db.add(user_message)
    db.commit()

    # Invoke the Agent. On failure a 502 is raised; the user message remains
    # persisted so the conversation history reflects the attempt.
    agent_response = await _invoke_agent(
        client, body.message, current_user.id, session.id, analysis_context
    )

    # When linked to an analysis, persist new charts/results onto that analysis
    # so they are added to the existing dashboard (Requirement 9.13).
    if session.analysis_session_id is not None:
        _persist_results(db, session.analysis_session_id, agent_response.analysis_results)
        _persist_charts(db, session.analysis_session_id, agent_response.charts)

    # Persist the assistant message with the artifacts captured in metadata so
    # the conversation can display them inline (Requirements 9.10, 9.13).
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=agent_response.response,
        metadata_={
            "charts": agent_response.charts,
            "analysis_results": agent_response.analysis_results,
            "report": agent_response.report,
            "agent_session_id": agent_response.session_id,
        },
    )
    db.add(assistant_message)

    # One user message + its reply == one turn (Requirement 9.17).
    session.turn_count += 1
    db.commit()
    db.refresh(assistant_message)
    db.refresh(session)

    return SendMessageResponse(
        message=ChatMessageResponse.model_validate(assistant_message),
        charts=agent_response.charts,
        analysis_results=agent_response.analysis_results,
        report=agent_response.report,
        turn_count=session.turn_count,
    )


@router.get("/sessions/{session_id}/messages", response_model=ChatHistoryResponse)
def get_messages(
    session_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    """Get the conversation history in chronological order.

    Requirements: 9.3
    """
    session = _get_chat_session_or_deny(db, session_id, current_user.id)

    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()

    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.get("/sessions/{session_id}/context", response_model=ConversationContextResponse)
def get_context(
    session_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationContextResponse:
    """Get the conversation context for a session.

    Returns the previously executed analyses, active dimensions (distinguishing
    system-generated vs user-requested), and generated charts derived from the
    linked analysis session. Lists are empty when no analysis is linked.
    Requirements: 9.15, 9.19, 9.22
    """
    session = _get_chat_session_or_deny(db, session_id, current_user.id)

    results, dimensions, charts = _linked_analysis_artifacts(
        db, session.analysis_session_id
    )

    return ConversationContextResponse(
        chat_session_id=session.id,
        analysis_session_id=session.analysis_session_id,
        turn_count=session.turn_count,
        executed_analyses=[ContextResultResponse.model_validate(r) for r in results],
        active_dimensions=[ContextDimensionResponse.model_validate(d) for d in dimensions],
        generated_charts=[ContextChartResponse.model_validate(c) for c in charts],
    )
