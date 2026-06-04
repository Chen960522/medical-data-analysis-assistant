import { jsxs as _jsxs, jsx as _jsx, Fragment as _Fragment } from "react/jsx-runtime";
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
import { SPACING } from '../../theme/tokens';
import { MAX_CONVERSATION_TURNS } from '../../types/chat';
import { MessageList } from './MessageList';
import { ChatComposer } from './ChatComposer';
const { Text } = Typography;
export function ChatPanel({ analysisSessionId, onArtifacts, height = '100%' }) {
    const notify = useNotify();
    const [sessionId, setSessionId] = useState(null);
    const [initializing, setInitializing] = useState(true);
    const [messages, setMessages] = useState([]);
    const [turnCount, setTurnCount] = useState(0);
    const [sending, setSending] = useState(false);
    const [limitReached, setLimitReached] = useState(false);
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
        }
        catch (err) {
            setSessionId(null);
            const message = err instanceof ApiError || err instanceof Error ? err.message : undefined;
            notify.error('无法创建对话会话', message);
        }
        finally {
            setInitializing(false);
        }
    }, [analysisSessionId, notify]);
    // Lazily create a session on mount and whenever the linked analysis changes.
    useEffect(() => {
        void createSession();
    }, [createSession]);
    /** Send a message to the Agent and append the reply with inline artifacts. */
    const handleSend = useCallback(async (text) => {
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
            setMessages((current) => current.map((msg) => msg.id === pendingId
                ? {
                    id: response.message.id,
                    role: 'assistant',
                    content: response.message.content,
                    charts,
                    analysisResults,
                }
                : msg));
            setTurnCount(response.turn_count);
            setLimitReached(response.turn_count >= MAX_CONVERSATION_TURNS);
            // Forward new artifacts to the parent dashboard (Req 9.13).
            if (onArtifacts && (charts.length > 0 || analysisResults.length > 0)) {
                onArtifacts({ charts, analysisResults });
            }
        }
        catch (err) {
            // Drop the optimistic user + pending bubbles so the user can retry.
            setMessages((current) => current.filter((msg) => msg.id !== userMsgId && msg.id !== pendingId));
            if (err instanceof ApiError && err.status === 409) {
                // Turn limit reached on the server (Req 9.17, 9.18).
                setLimitReached(true);
                setTurnCount(MAX_CONVERSATION_TURNS);
                notify.warning(err.message);
            }
            else {
                const message = err instanceof ApiError || err instanceof Error ? err.message : undefined;
                notify.error('消息发送失败', message);
            }
        }
        finally {
            setSending(false);
        }
    }, [sessionId, sending, limitReached, onArtifacts, notify]);
    const turnIndicator = (_jsxs(Tag, { color: limitReached ? 'error' : 'blue', children: ["\u8F6E\u6B21\uFF1A", turnCount, " / ", MAX_CONVERSATION_TURNS] }));
    return (_jsx(Card, { title: _jsxs(Space, { children: [_jsx(MessageOutlined, {}), _jsx("span", { children: "\u5BF9\u8BDD\u5F0F\u5206\u6790" })] }), extra: turnIndicator, variant: "outlined", style: { height, display: 'flex', flexDirection: 'column' }, styles: {
            body: {
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                padding: 0,
            },
        }, children: initializing ? (_jsx("div", { style: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }, children: _jsx(LoadingIndicator, { tip: "\u6B63\u5728\u51C6\u5907\u5BF9\u8BDD\u2026", size: "default" }) })) : sessionId ? (_jsxs(_Fragment, { children: [_jsx(MessageList, { messages: messages }), limitReached ? (_jsx(Alert, { type: "warning", showIcon: true, style: { margin: `0 ${SPACING.md}px ${SPACING.sm}px` }, message: `对话已达到最大轮次限制（${MAX_CONVERSATION_TURNS} 轮）`, description: "\u5DF2\u751F\u6210\u7684\u5206\u6790\u7ED3\u679C\u4ECD\u4F1A\u4FDD\u7559\u5728\u4EEA\u8868\u76D8\u4E2D\u3002\u5F00\u59CB\u65B0\u5BF9\u8BDD\u4EE5\u7EE7\u7EED\u63A2\u7D22\u3002", action: _jsx(Button, { size: "small", type: "primary", icon: _jsx(PlusOutlined, {}), onClick: () => void createSession(), children: "\u5F00\u59CB\u65B0\u5BF9\u8BDD" }) })) : null, _jsx("div", { style: { borderTop: '1px solid rgba(0,0,0,0.06)' }, children: _jsx(ChatComposer, { onSend: (message) => void handleSend(message), sending: sending, disabled: limitReached }) })] })) : (_jsxs("div", { style: {
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: SPACING.md,
                padding: SPACING.lg,
            }, children: [_jsx(Text, { type: "secondary", children: "\u5BF9\u8BDD\u4F1A\u8BDD\u521B\u5EFA\u5931\u8D25\u3002" }), _jsx(Button, { type: "primary", onClick: () => void createSession(), children: "\u91CD\u8BD5" })] })) }));
}
export default ChatPanel;
