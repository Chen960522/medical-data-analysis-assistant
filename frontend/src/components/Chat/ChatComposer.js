import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Conversation message composer.
 *
 * A multiline text input with a send button for submitting natural-language
 * messages to the Agent (Req 9.2). Pressing Enter sends the message while
 * Shift+Enter inserts a newline. The input and send button are disabled while a
 * request is in flight (showing a sending indicator) and when the conversation
 * has reached its turn limit (Req 9.17).
 */
import { useState } from 'react';
import { Button, Input, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { SPACING } from '../../theme/tokens';
export function ChatComposer({ onSend, sending, disabled = false, placeholder = '输入消息，按 Enter 发送，Shift+Enter 换行…', }) {
    const [value, setValue] = useState('');
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
    const handleKeyDown = (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
        }
    };
    return (_jsxs(Space.Compact, { block: true, style: { padding: SPACING.sm, gap: SPACING.sm, alignItems: 'flex-end' }, children: [_jsx(Input.TextArea, { value: value, onChange: (event) => setValue(event.target.value), onKeyDown: handleKeyDown, placeholder: placeholder, disabled: disabled, autoSize: { minRows: 1, maxRows: 4 }, "aria-label": "\u5BF9\u8BDD\u8F93\u5165\u6846" }), _jsx(Button, { type: "primary", icon: _jsx(SendOutlined, {}), loading: sending, disabled: !canSend, onClick: submit, "aria-label": "\u53D1\u9001\u6D88\u606F", children: "\u53D1\u9001" })] }));
}
export default ChatComposer;
