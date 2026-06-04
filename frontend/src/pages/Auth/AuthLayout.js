import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Centered authentication layout.
 *
 * Shared shell for the login and registration pages, presenting a branded,
 * centered card consistent with the platform's design system (Req 12.9).
 */
import { Card, Typography } from 'antd';
import { SPACING } from '../../theme/tokens';
const { Title, Text } = Typography;
export function AuthLayout({ title, subtitle, children }) {
    return (_jsx("div", { style: {
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: SPACING.lg,
            background: 'var(--ant-color-bg-layout, #f5f7fa)',
        }, children: _jsxs(Card, { style: { width: '100%', maxWidth: 420 }, variant: "outlined", children: [_jsxs("div", { style: { textAlign: 'center', marginBottom: SPACING.lg }, children: [_jsx(Title, { level: 2, style: { marginBottom: SPACING.xs }, children: title }), subtitle ? _jsx(Text, { type: "secondary", children: subtitle }) : null] }), children] }) }));
}
export default AuthLayout;
