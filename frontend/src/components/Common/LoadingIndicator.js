import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Contextual loading indicator.
 *
 * Displays a spinner with descriptive text explaining the current operation
 * (file upload, analysis execution, translation processing, etc.) per Req 12.14.
 * The descriptive text is also exposed to assistive tech via aria-live.
 */
import { Spin, Typography } from 'antd';
import { SPACING } from '../../theme/tokens';
const { Text } = Typography;
export function LoadingIndicator({ tip = '加载中…', size = 'large', fullHeight = false, style, }) {
    const containerStyle = {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: SPACING.md,
        padding: SPACING.xl,
        minHeight: fullHeight ? '60vh' : undefined,
        ...style,
    };
    return (_jsxs("div", { style: containerStyle, role: "status", "aria-live": "polite", children: [_jsx(Spin, { size: size }), tip ? _jsx(Text, { type: "secondary", children: tip }) : null] }));
}
export default LoadingIndicator;
