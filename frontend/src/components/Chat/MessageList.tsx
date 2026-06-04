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
import type { DisplayMessage } from '../../types/chat';
import { MessageBubble } from './MessageBubble';

export interface MessageListProps {
  messages: DisplayMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the newest message whenever the conversation changes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: SPACING.md,
      }}
    >
      {messages.length === 0 ? (
        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="向 AI 提问以从新的维度探索数据，例如「按年龄分组比较血压」。"
          />
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
}

export default MessageList;
