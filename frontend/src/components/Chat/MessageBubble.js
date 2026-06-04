import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Conversation message bubble.
 *
 * Renders a single conversation message with clear visual distinction between
 * User messages (right-aligned, primary-tinted bubble) and AI replies
 * (left-aligned, neutral bubble) (Req 9.3). Assistant messages that carry
 * charts and/or analysis results render them inline within the bubble: charts
 * via {@link ChartCard} (which provides fullscreen expand + export, Req
 * 9.10-9.12) and analysis results via {@link InlineAnalysisResults}.
 */
import { Avatar, Space, Spin, Typography } from 'antd';
import { RobotOutlined, UserOutlined } from '@ant-design/icons';
import { ChartCard } from '../Charts';
import { GEOMETRY, PALETTE, SPACING } from '../../theme/tokens';
import { useThemeStore } from '../../stores/themeStore';
import { InlineAnalysisResults } from './InlineAnalysisResults';
const { Text } = Typography;
export function MessageBubble({ message }) {
    const mode = useThemeStore((state) => state.mode);
    const isUser = message.role === 'user';
    const isDark = mode === 'dark';
    // User bubbles are primary-tinted; assistant bubbles use a neutral surface.
    // Colors are chosen for AA contrast in both themes (Req 12.4).
    const userBg = PALETTE.primary;
    const userColor = PALETTE.neutral.white;
    const assistantBg = isDark ? PALETTE.neutral.gray7 : PALETTE.neutral.gray1;
    const assistantColor = isDark ? PALETTE.neutral.gray1 : PALETTE.neutral.gray8;
    const hasArtifacts = message.charts.length > 0 || message.analysisResults.length > 0;
    return (_jsxs("div", { style: {
            display: 'flex',
            flexDirection: isUser ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
            gap: SPACING.sm,
            marginBottom: SPACING.md,
        }, children: [_jsx(Avatar, { size: "small", icon: isUser ? _jsx(UserOutlined, {}) : _jsx(RobotOutlined, {}), style: {
                    flexShrink: 0,
                    backgroundColor: isUser ? PALETTE.primary : PALETTE.neutral.gray4,
                }, "aria-label": isUser ? '用户消息' : 'AI 回复' }), _jsxs("div", { style: {
                    // Bubbles with artifacts get more width to comfortably fit charts.
                    maxWidth: hasArtifacts ? '92%' : '78%',
                    minWidth: 0,
                }, children: [_jsx("div", { style: {
                            backgroundColor: isUser ? userBg : assistantBg,
                            color: isUser ? userColor : assistantColor,
                            padding: `${SPACING.sm}px ${SPACING.md}px`,
                            borderRadius: GEOMETRY.borderRadiusLg,
                            // Slightly square the corner nearest the avatar for a chat look.
                            borderTopRightRadius: isUser ? GEOMETRY.borderRadius / 2 : GEOMETRY.borderRadiusLg,
                            borderTopLeftRadius: isUser ? GEOMETRY.borderRadiusLg : GEOMETRY.borderRadius / 2,
                            wordBreak: 'break-word',
                            whiteSpace: 'pre-wrap',
                        }, children: message.pending ? (_jsxs(Space, { size: SPACING.sm, children: [_jsx(Spin, { size: "small" }), _jsx(Text, { style: { color: assistantColor }, children: "\u6B63\u5728\u601D\u8003\u2026" })] })) : (_jsx(Text, { style: { color: isUser ? userColor : assistantColor }, children: message.content })) }), !message.pending && hasArtifacts ? (_jsxs(Space, { direction: "vertical", size: SPACING.sm, style: { width: '100%', marginTop: SPACING.sm }, children: [message.charts.map((chart) => (_jsx(ChartCard, { chart: chart, height: 260 }, chart.id))), _jsx(InlineAnalysisResults, { results: message.analysisResults })] })) : null] })] }));
}
export default MessageBubble;
