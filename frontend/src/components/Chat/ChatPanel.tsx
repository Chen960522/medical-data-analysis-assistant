/**
 * Persistent conversational analysis panel.
 *
 * A persistent chat window intended to sit alongside the data-analysis view
 * (Req 9.1, 9.4). It lazily creates a chat session (optionally linked to an
 * analysis, Req 9.14), renders the conversation history with clear user/AI
 * distinction (Req 9.3), sends natural-language messages to the Agent and
 * displays the returned charts and analysis results inline (Req 9.10-9.12),
 * forwards new artifacts to the parent so they are added to the dashboard
 * (Req 9.13), and enforces the 50-turn conversation limit with a notice and a
 * "start new conversation" affordance that preserves accumulated results
 * (Req 9.17, 9.18).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Space, Tag, Typography } from 'antd';
import { MessageOutlined, PlusOutlined } from '@ant-design/icons';

import { LoadingIndicator } from '../Common';
import { useNotify } from '../../hooks/useNotify';
import { ApiError } from '../../services/apiClient';
import { chatService, normalizeCharts } from '../../services/chatService';
import {
  buildReferencePrompt,
  useLiteratureReferenceStore,
} from '../../stores/literatureReferenceStore';
import { SPACING } from '../../theme/tokens';
import type { ChartData } from '../Charts';
import { MAX_CONVERSATION_TURNS } from '../../types/chat';
import type { DisplayMessage } from '../../types/chat';
import { MessageList } from './MessageList';
import { ChatComposer } from './ChatComposer';

const { Text } = Typography;

export interface ChatPanelProps {
  /** Optional analysis session to link the conversation to (Req 9.14). */
  analysisSessionId?: string;
  /** Called when the agent returns new charts/results so the parent can refresh the dashboard (Req 9.13). */
  onArtifacts?: (payload: {
    charts: ChartData[];
    analysisResults: Record<string, unknown>[];
  }) => void;
  /** Optional fixed height; defaults to filling its container. */
  height?: number | string;
}

export function ChatPanel({ analysisSessionId, onArtifacts, height = '100%' }: ChatPanelProps) {
  const notify = useNotify();
  // Stable ref so createSession's useCallback doesn't re-fire on every render.
  const notifyRef = useRef(notify);
  notifyRef.current = notify;

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [turnCount, setTurnCount] = useState(0);
  const [sending, setSending] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  /** Seed text fed into the composer (e.g. a literature methodology reference). */
  const [seedText, setSeedText] = useState<string | undefined>(undefined);

  const pendingReference = useLiteratureReferenceStore((state) => state.pending);
  const consumeReference = useLiteratureReferenceStore((state) => state.consumeReference);

  // Used to generate stable keys for optimistic (client-only) messages.
  const tempIdRef = useRef(0);
  const nextTempId = () => `temp-${(tempIdRef.current += 1)}`;

  /** Create a fresh chat session, resetting the local conversation state. */
  const createSession = useCallback(async () => {
    setInitializing(true);
    setMessages([]);
    setTurnCount(0);
    setLimitReached(false);
    try {
      const session = await chatService.createSession(analysisSessionId);
      setSessionId(session.id);
      setTurnCount(session.turn_count);
      setLimitReached(session.turn_count >= MAX_CONVERSATION_TURNS);
    } catch (err) {
      setSessionId(null);
      const message = err instanceof ApiError || err instanceof Error ? err.message : undefined;
      notifyRef.current.error('无法创建对话会话', message);
    } finally {
      setInitializing(false);
    }
  }, [analysisSessionId]); // notify intentionally excluded via notifyRef to prevent infinite loop

  // Lazily create a session on mount and whenever the linked analysis changes.
  useEffect(() => {
    void createSession();
  }, [createSession]);

  // Pick up a literature methodology reference staged from the Literature module
  // and seed the composer so the User can ask the AI to apply a similar
  // analytical approach (Req 10.44, 10.45). The reference is consumed (cleared)
  // so it is only applied once.
  useEffect(() => {
    if (pendingReference) {
      const reference = consumeReference();
      if (reference) {
        setSeedText(buildReferencePrompt(reference));
        notify.info('已引入文献方法学，可在对话中编辑后发送');
      }
    }
  }, [pendingReference, consumeReference, notify]);

  /** Send a message to the Agent and append the reply with inline artifacts. */
  const handleSend = useCallback(
    async (text: string) => {
      if (!sessionId || sending || limitReached) {
        return;
      }

      // Optimistically append the user's message and a pending assistant bubble.
      const userMsgId = nextTempId();
      const pendingId = nextTempId();
      setMessages((current) => [
        ...current,
        { id: userMsgId, role: 'user', content: text, charts: [], analysisResults: [] },
        { id: pendingId, role: 'assistant', content: '', charts: [], analysisResults: [], pending: true },
      ]);
      setSending(true);

      try {
        const response = await chatService.sendMessage(sessionId, text);
        const charts = normalizeCharts(response.charts);
        const analysisResults = response.analysis_results ?? [];

        // Replace the pending bubble with the real assistant reply + artifacts.
        setMessages((current) =>
          current.map((msg) =>
            msg.id === pendingId
              ? {
                  id: response.message.id,
                  role: 'assistant',
                  content: response.message.content,
                  charts,
                  analysisResults,
                }
              : msg,
          ),
        );
        setTurnCount(response.turn_count);
        setLimitReached(response.turn_count >= MAX_CONVERSATION_TURNS);

        // Forward new artifacts to the parent dashboard (Req 9.13).
        if (onArtifacts && (charts.length > 0 || analysisResults.length > 0)) {
          onArtifacts({ charts, analysisResults });
        }
      } catch (err) {
        // Drop the optimistic user + pending bubbles so the user can retry.
        setMessages((current) => current.filter((msg) => msg.id !== userMsgId && msg.id !== pendingId));

        if (err instanceof ApiError && err.status === 409) {
          // Turn limit reached on the server (Req 9.17, 9.18).
          setLimitReached(true);
          setTurnCount(MAX_CONVERSATION_TURNS);
          notify.warning(err.message);
        } else {
          const message = err instanceof ApiError || err instanceof Error ? err.message : undefined;
          notify.error('消息发送失败', message);
        }
      } finally {
        setSending(false);
      }
    },
    [sessionId, sending, limitReached, onArtifacts, notify],
  );

  const turnIndicator = (
    <Tag color={limitReached ? 'error' : 'blue'}>
      轮次：{turnCount} / {MAX_CONVERSATION_TURNS}
    </Tag>
  );

  return (
    <Card
      title={
        <Space>
          <MessageOutlined />
          <span>对话式分析</span>
        </Space>
      }
      extra={turnIndicator}
      variant="outlined"
      style={{ height, display: 'flex', flexDirection: 'column' }}
      styles={{
        body: {
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
        },
      }}
    >
      {initializing ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <LoadingIndicator tip="正在准备对话…" size="default" />
        </div>
      ) : sessionId ? (
        <>
          <MessageList messages={messages} />

          {/* Turn-limit notice with a start-new-conversation action (Req 9.18). */}
          {limitReached ? (
            <Alert
              type="warning"
              showIcon
              style={{ margin: `0 ${SPACING.md}px ${SPACING.sm}px` }}
              message={`对话已达到最大轮次限制（${MAX_CONVERSATION_TURNS} 轮）`}
              description="已生成的分析结果仍会保留在仪表盘中。开始新对话以继续探索。"
              action={
                <Button
                  size="small"
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => void createSession()}
                >
                  开始新对话
                </Button>
              }
            />
          ) : null}

          <div style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
            <ChatComposer
              onSend={(message) => void handleSend(message)}
              sending={sending}
              disabled={limitReached}
              seedText={seedText}
            />
          </div>
        </>
      ) : (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: SPACING.md,
            padding: SPACING.lg,
          }}
        >
          <Text type="secondary">对话会话创建失败。</Text>
          <Button type="primary" onClick={() => void createSession()}>
            重试
          </Button>
        </div>
      )}
    </Card>
  );
}

export default ChatPanel;
