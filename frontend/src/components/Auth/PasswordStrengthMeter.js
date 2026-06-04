import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Password strength meter.
 *
 * Visualizes how well a password meets the complexity policy (Req 8.4) and
 * lists each rule with a pass/fail indicator. Status is conveyed with both an
 * icon and text, not color alone (Req 12.34).
 */
import { Progress, Space, Typography } from 'antd';
import { CheckCircleTwoTone, CloseCircleOutlined } from '@ant-design/icons';
import { PASSWORD_MIN_LENGTH, checkPassword, passwordStrength } from '../../utils/validation';
import { SPACING } from '../../theme/tokens';
const { Text } = Typography;
const STRENGTH_META = {
    weak: { percent: 33, color: '#ff4d4f', label: '弱' },
    medium: { percent: 66, color: '#faad14', label: '中' },
    strong: { percent: 100, color: '#52c41a', label: '强' },
};
function Rule({ ok, text }) {
    return (_jsxs(Space, { size: 4, children: [ok ? (_jsx(CheckCircleTwoTone, { twoToneColor: "#52c41a" })) : (_jsx(CloseCircleOutlined, { style: { color: '#bfbfbf' } })), _jsx(Text, { type: ok ? 'success' : 'secondary', style: { fontSize: 12 }, children: text })] }));
}
export function PasswordStrengthMeter({ password }) {
    if (!password) {
        return null;
    }
    const checks = checkPassword(password);
    const meta = STRENGTH_META[passwordStrength(password)];
    return (_jsxs("div", { style: { marginTop: SPACING.sm }, "aria-live": "polite", children: [_jsx(Progress, { percent: meta.percent, strokeColor: meta.color, showInfo: false, size: "small", "aria-label": `密码强度：${meta.label}` }), _jsxs(Text, { style: { fontSize: 12 }, type: "secondary", children: ["\u5BC6\u7801\u5F3A\u5EA6\uFF1A", meta.label] }), _jsxs("div", { style: {
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: `${SPACING.xs}px ${SPACING.md}px`,
                    marginTop: SPACING.xs,
                }, children: [_jsx(Rule, { ok: checks.length, text: `至少 ${PASSWORD_MIN_LENGTH} 个字符` }), _jsx(Rule, { ok: checks.uppercase, text: "\u542B\u5927\u5199\u5B57\u6BCD" }), _jsx(Rule, { ok: checks.lowercase, text: "\u542B\u5C0F\u5199\u5B57\u6BCD" }), _jsx(Rule, { ok: checks.digit, text: "\u542B\u6570\u5B57" }), _jsx(Rule, { ok: checks.special, text: "\u542B\u7279\u6B8A\u5B57\u7B26" })] })] }));
}
export default PasswordStrengthMeter;
