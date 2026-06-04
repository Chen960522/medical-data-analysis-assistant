import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Conversation message list.
 *
 * Renders the conversation history in chronological order (Req 9.3) inside a
 * scrollable container that auto-scrolls to the newest message whenever the
 * list changes. Shows an empty-state hint before the first message is sent.
 */
import { useEffect, useRef } from 'react';
import { Empty } from 'antd';
import { SPACING } from '../../theme/tokens';
import { MessageBubble } from './MessageBubble';
export function MessageList({ messages }) {
    const bottomRef = useRef(null);
    // Auto-scroll to the newest message whenever the conversation changes.
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [messages]);
    return (_jsx("div", { style: {
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: SPACING.md,
        }, children: messages.length === 0 ? (_jsx("div", { style: { height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }, children: _jsx(Empty, { image: Empty.PRESENTED_IMAGE_SIMPLE, description: "\u5411 AI \u63D0\u95EE\u4EE5\u4ECE\u65B0\u7684\u7EF4\u5EA6\u63A2\u7D22\u6570\u636E\uFF0C\u4F8B\u5982\u300C\u6309\u5E74\u9F84\u5206\u7EC4\u6BD4\u8F83\u8840\u538B\u300D\u3002" }) })) : (_jsxs(_Fragment, { children: [messages.map((message) => (_jsx(MessageBubble, { message: message }, message.id))), _jsx("div", { ref: bottomRef })] })) }));
}
export default MessageList;
