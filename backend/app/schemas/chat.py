"""Chat (conversational analysis) request/response schemas.

Pydantic models for the conversation API (create session, send message, fetch
history, fetch conversation context). Mirrors the response-model style used in
``app/schemas/analysis.py`` (``model_config = {"from_attributes": True}``).

The :class:`ChatMessage` model stores its JSON payload on the ``metadata_``
attribute (mapped to the DB column ``"metadata"``), so the response schema reads
that attribute via a ``validation_alias`` while exposing it as ``metadata``.

Requirements: 9.1-9.22
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateChatSessionRequest(BaseModel):
    """Request body for creating a conversation session.

    ``analysis_session_id`` optionally links the conversation to an existing
    analysis so its results/charts/dimensions form the conversation context
    (Requirements 9.14, 9.15).
    """

    analysis_session_id: Optional[uuid.UUID] = None


class ChatSessionResponse(BaseModel):
    """Response schema for a chat session record."""

    id: uuid.UUID
    analysis_session_id: Optional[uuid.UUID] = None
    turn_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    """Request body for sending a natural-language message to the Agent."""

    message: str = Field(min_length=1)


class ChatMessageResponse(BaseModel):
    """Response schema for a single chat message.

    Reads the ORM ``metadata_`` attribute via ``validation_alias`` and exposes
    it as ``metadata`` in the serialized output.
    """

    id: uuid.UUID
    role: str
    content: str
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SendMessageResponse(BaseModel):
    """Response schema for sending a message.

    Returns the persisted assistant message plus the artifacts produced by the
    Agent for inline display (Requirements 9.10, 9.13) and the updated
    ``turn_count`` for the session (Requirement 9.17).
    """

    message: ChatMessageResponse
    charts: list[dict[str, Any]]
    analysis_results: list[dict[str, Any]]
    report: Optional[dict[str, Any]] = None
    turn_count: int


class ChatHistoryResponse(BaseModel):
    """Response schema for conversation history (chronological order)."""

    messages: list[ChatMessageResponse]
    total: int


class ContextResultResponse(BaseModel):
    """A previously executed analysis result within the conversation context."""

    id: uuid.UUID
    result_type: str
    result_data: dict[str, Any]

    model_config = {"from_attributes": True}


class ContextDimensionResponse(BaseModel):
    """An active analysis dimension, distinguishing system vs user origin.

    ``dimension_type`` is ``"system"`` for AI-generated default dimensions and
    ``"user"`` for User-requested custom dimensions (Requirement 9.22).
    """

    id: uuid.UUID
    name: str
    dimension_type: str

    model_config = {"from_attributes": True}


class ContextChartResponse(BaseModel):
    """A generated chart within the conversation context."""

    id: uuid.UUID
    chart_type: str
    title: str

    model_config = {"from_attributes": True}


class ConversationContextResponse(BaseModel):
    """Response schema for the conversation context of a session.

    Aggregates the previously executed analyses, active dimensions (split by
    system/user origin), and generated charts from the linked analysis session
    (Requirements 9.15, 9.19, 9.22). When no analysis is linked, the lists are
    empty.
    """

    chat_session_id: uuid.UUID
    analysis_session_id: Optional[uuid.UUID] = None
    turn_count: int
    executed_analyses: list[ContextResultResponse]
    active_dimensions: list[ContextDimensionResponse]
    generated_charts: list[ContextChartResponse]
