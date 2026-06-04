import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Analysis progress indicator.
 *
 * Shows the current analysis stage label and a percentage progress bar while an
 * analysis is in flight (Req 3.7). The backend `/start` endpoint is synchronous
 * and returns full results once complete, so this component renders an
 * indeterminate in-progress state during the request; when a concrete
 * `AnalysisStatusResponse` is available its `stage` and `progress` are shown.
 */
import { Card, Progress, Space, Typography } from 'antd';
import { LoadingIndicator } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
export function AnalysisProgress({ status }) {
    const stage = status?.stage ?? '分析进行中';
    // Without a concrete status the request is in flight; show an active bar that
    // does not imply completion.
    const percent = status?.progress ?? 30;
    const isFailed = status?.status === 'failed';
    return (_jsx(Card, { variant: "outlined", "aria-live": "polite", children: _jsxs(Space, { direction: "vertical", style: { width: '100%' }, size: SPACING.sm, children: [_jsx(LoadingIndicator, { tip: stage, size: "default", style: { padding: SPACING.md } }), _jsxs("div", { children: [_jsxs(Text, { type: "secondary", children: ["\u5F53\u524D\u9636\u6BB5\uFF1A", stage] }), _jsx(Progress, { percent: percent, status: isFailed ? 'exception' : 'active', "aria-label": `分析进度 ${percent}%` })] })] }) }));
}
export default AnalysisProgress;
