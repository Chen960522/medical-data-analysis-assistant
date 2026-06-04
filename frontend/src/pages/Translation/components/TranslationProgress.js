import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Translation progress indicator (Req 11.28).
 *
 * While full-document translation is in progress, displays a percentage
 * progress bar with descriptive text (Req 12.14). The backend translate call is
 * synchronous, so when a concrete percentage is not yet known the bar runs in an
 * active/indeterminate state; an optional polled `percent` from
 * `GET /translation/{id}/status` is shown when available.
 */
import { Progress, Space, Typography } from 'antd';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
export function TranslationProgress({ percent }) {
    // When the percentage is unknown, keep the bar active near the start so the
    // user sees ongoing activity (Req 12.14) without implying completion.
    const value = typeof percent === 'number' ? Math.min(100, Math.max(0, Math.round(percent))) : 10;
    return (_jsxs(Space, { direction: "vertical", size: SPACING.sm, style: { width: '100%' }, "aria-live": "polite", children: [_jsx(Text, { type: "secondary", children: "\u6B63\u5728\u7FFB\u8BD1\u6587\u6863\uFF0C\u8BF7\u7A0D\u5019\u2026" }), _jsx(Progress, { percent: value, status: "active" })] }));
}
export default TranslationProgress;
