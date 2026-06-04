/**
 * Conversation message composer.
 *
 * A multiline text input with a send button for submitting natural-language
 * messages to the Agent (Req 9.2). Pressing Enter sends the message while
 * Shift+Enter inserts a newline. The input and send button are disabled while a
 * request is in flight (showing a sending indicator) and when the conversation
 * has reached its turn limit (Req 9.17).
 */

import { useEffect, useState } from 'react';
import { Button, Input, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import type { KeyboardEvent } from 'react';

import { SPACING } from '../../theme/tokens';

export interface ChatComposerProps {
  /** Invoked with the trimmed message text when the User sends. */
  onSend: (message: string) => void;
  /** True while a send request is in flight. */
  sending: boolean;
  /** Disables input entirely (e.g. turn limit reached or no session). */
  disabled?: boolean;
  /** Placeholder text for the input. */
  placeholder?: string;
  /**
   * Text to seed the input with (e.g. a literature methodology reference,
   * Req 10.45). Each distinct value is applied once into the editable input so
   * the User can review/edit it before sending.
   */
  seedText?: string;
}

export function ChatComposer({
  onSend,
  sending,
  disabled = false,
  placeholder = '输入消息，按 Enter 发送，Shift+Enter 换行…',
  seedText,
}: ChatComposerProps) {
  const [value, setValue] = useState('');

  // Apply an externally provided seed into the editable input. Keyed on the
  // seed text so a new reference replaces the field, while user edits afterward
  // are preserved (the effect only re-runs when seedText changes).
  useEffect(() => {
    if (seedText) {
      setValue(seedText);
    }
  }, [seedText]);

  const inputDisabled = disabled || sending;
  const canSend = value.trim().length > 0 && !inputDisabled;

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || inputDisabled) {
      return;
    }
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <Space.Compact block style={{ padding: SPACING.sm, gap: SPACING.sm, alignItems: 'flex-end' }}>
      <Input.TextArea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        autoSize={{ minRows: 1, maxRows: 4 }}
        aria-label="对话输入框"
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        loading={sending}
        disabled={!canSend}
        onClick={submit}
        aria-label="发送消息"
      >
        发送
      </Button>
    </Space.Compact>
  );
}

export default ChatComposer;
