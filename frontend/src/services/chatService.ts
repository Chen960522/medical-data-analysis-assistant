/**
 * Chat API service.
 *
 * Wraps the `/chat` endpoints defined in `backend/app/api/v1/chat.py` for the
 * Agent-driven conversation lifecycle: creating a session, sending a message
 * (returning analysis results/charts inline), fetching the conversation
 * history, and fetching the conversation context (Req 9.1-9.22).
 *
 * It also normalizes the raw chart payloads returned by `send` into the
 * `ChartData` shape consumed by the Charts library (`ChartCard`/`ChartGrid`),
 * supporting both bare ECharts option dicts and `{ chart_type, title, option }`
 * wrappers (mirrors `_persist_charts` in `backend/app/api/v1/analysis.py`).
 */

import type { EChartsOption } from 'echarts-for-react';

import { apiClient } from './apiClient';
import type { ChartData } from '../components/Charts';
import type {
  ChatHistoryResponse,
  ChatSession,
  ConversationContext,
  CreateChatSessionRequest,
  RawChartPayload,
  SendMessageResponse,
} from '../types/chat';

/** Type guard for a plain JSON object. */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Derive a chart title from a bare ECharts option (its `title.text`). */
function deriveTitle(option: Record<string, unknown>): string {
  const title = option.title;
  if (isPlainObject(title) && typeof title.text === 'string' && title.text) {
    return title.text;
  }
  if (typeof title === 'string' && title) {
    return title;
  }
  return '图表';
}

/** Generate a stable-enough client id for a chart lacking a server id. */
function generateChartId(index: number): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `chat-chart-${Date.now()}-${index}`;
}

/**
 * Normalize a single raw chart payload into {@link ChartData}.
 *
 * Supports a `{ chart_type, title, option }` wrapper as well as a bare ECharts
 * option dict, deriving the type/title from the option when not provided.
 */
function normalizeChart(raw: RawChartPayload, index: number): ChartData | null {
  if (!isPlainObject(raw)) {
    return null;
  }

  const isWrapper = isPlainObject(raw.option);
  const option = (isWrapper ? raw.option : raw) as Record<string, unknown>;

  const wrapperType = typeof raw.chart_type === 'string' ? raw.chart_type : undefined;
  const chartType = wrapperType && wrapperType.length > 0 ? wrapperType : 'chart';

  const wrapperTitle = isWrapper && typeof raw.title === 'string' ? raw.title : undefined;
  const title = wrapperTitle && wrapperTitle.length > 0 ? wrapperTitle : deriveTitle(option);

  const id = typeof raw.id === 'string' && raw.id.length > 0 ? raw.id : generateChartId(index);

  return {
    id,
    chart_type: chartType,
    title,
    echarts_option: option as EChartsOption,
  };
}

/**
 * Normalize the raw chart payloads from a send response into {@link ChartData}.
 *
 * Invalid entries are dropped so a malformed chart never breaks rendering.
 */
export function normalizeCharts(charts: RawChartPayload[] | undefined | null): ChartData[] {
  if (!Array.isArray(charts)) {
    return [];
  }
  const normalized: ChartData[] = [];
  charts.forEach((raw, index) => {
    const chart = normalizeChart(raw, index);
    if (chart) {
      normalized.push(chart);
    }
  });
  return normalized;
}

export const chatService = {
  /** Create a conversation session, optionally linked to an analysis (Req 9.1, 9.14). */
  createSession: (analysisSessionId?: string) => {
    const body: CreateChatSessionRequest = {};
    if (analysisSessionId) {
      body.analysis_session_id = analysisSessionId;
    }
    return apiClient.post<ChatSession>('/chat/sessions', body);
  },

  /** Send a message to the Agent and receive its reply + inline artifacts (Req 9.2, 9.10). */
  sendMessage: (sessionId: string, message: string) =>
    apiClient.post<SendMessageResponse>(`/chat/sessions/${sessionId}/messages`, { message }),

  /** Get the conversation history in chronological order (Req 9.3). */
  getMessages: (sessionId: string) =>
    apiClient.get<ChatHistoryResponse>(`/chat/sessions/${sessionId}/messages`),

  /** Get the conversation context for a session (Req 9.15, 9.19). */
  getContext: (sessionId: string) =>
    apiClient.get<ConversationContext>(`/chat/sessions/${sessionId}/context`),
};
