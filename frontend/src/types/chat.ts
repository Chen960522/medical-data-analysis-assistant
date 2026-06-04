/**
 * Chat (conversational analysis) TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/chat.py` for the
 * Agent-driven conversation API (create session, send message, fetch history,
 * fetch conversation context). These power the persistent Chat_Interface that
 * sits alongside the analysis view (Req 9.1-9.4, 9.10-9.13, 9.17-9.18).
 */

import type { ChartData } from '../components/Charts';

/** Maximum number of conversation turns per analysis session (Req 9.17). */
export const MAX_CONVERSATION_TURNS = 50;

/** Author of a chat message. */
export type ChatRole = 'user' | 'assistant';

/**
 * A conversation session record.
 *
 * Mirrors `ChatSessionResponse`; `analysis_session_id` links the conversation
 * to an existing analysis so its results form the context (Req 9.14).
 */
export interface ChatSession {
  id: string;
  analysis_session_id?: string | null;
  turn_count: number;
  created_at: string;
}

/**
 * A single chat message.
 *
 * Mirrors `ChatMessageResponse`. The assistant's `metadata` may also carry the
 * `charts` / `analysis_results` produced for the turn (Req 9.10, 9.13).
 */
export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

/** Request body for `POST /chat/sessions`. */
export interface CreateChatSessionRequest {
  analysis_session_id?: string;
}

/** Request body for `POST /chat/sessions/{session_id}/messages`. */
export interface SendMessageRequest {
  message: string;
}

/**
 * A raw chart payload as delivered by the backend.
 *
 * The backend may return either a bare ECharts option dict OR a
 * `{ chart_type, title, option }` wrapper (see `_persist_charts` in
 * `backend/app/api/v1/analysis.py`). Normalize via {@link normalizeCharts}.
 */
export type RawChartPayload = Record<string, unknown>;

/**
 * Response from `POST /chat/sessions/{session_id}/messages`.
 *
 * Mirrors `SendMessageResponse`: the persisted assistant message plus the raw
 * artifacts produced by the Agent and the updated turn count (Req 9.17).
 */
export interface SendMessageResponse {
  message: ChatMessage;
  charts: RawChartPayload[];
  analysis_results: Record<string, unknown>[];
  report?: Record<string, unknown> | null;
  turn_count: number;
}

/** Response from `GET /chat/sessions/{session_id}/messages`. */
export interface ChatHistoryResponse {
  messages: ChatMessage[];
  total: number;
}

/** A previously executed analysis result within the conversation context. */
export interface ContextResult {
  id: string;
  result_type: string;
  result_data: Record<string, unknown>;
}

/** An active analysis dimension within the conversation context (Req 9.22). */
export interface ContextDimension {
  id: string;
  name: string;
  dimension_type: string;
}

/** A generated chart within the conversation context. */
export interface ContextChart {
  id: string;
  chart_type: string;
  title: string;
}

/** Response from `GET /chat/sessions/{session_id}/context`. */
export interface ConversationContext {
  chat_session_id: string;
  analysis_session_id?: string | null;
  turn_count: number;
  executed_analyses: ContextResult[];
  active_dimensions: ContextDimension[];
  generated_charts: ContextChart[];
}

/**
 * A conversation message enriched for display.
 *
 * Wraps a {@link ChatMessage} with its normalized inline artifacts so the
 * conversation history can render charts and analysis results inline and keep
 * them as the history grows (Req 9.10).
 */
export interface DisplayMessage {
  id: string;
  role: ChatRole;
  content: string;
  /** Normalized charts to render inline via `ChartCard` (Req 9.10-9.12). */
  charts: ChartData[];
  /** Raw analysis result payloads to render inline (Req 9.10). */
  analysisResults: Record<string, unknown>[];
  /** True while the assistant reply for this turn is still in flight. */
  pending?: boolean;
}
