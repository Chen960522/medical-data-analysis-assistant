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
import type { DisplayMessage } from '../../types/chat';
import { InlineAnalysisResults } from './InlineAnalysisResults';

const { Text } = Typography;

export interface MessageBubbleProps {
  message: DisplayMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
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

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
        gap: SPACING.sm,
        marginBottom: SPACING.md,
      }}
    >
      <Avatar
        size="small"
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          flexShrink: 0,
          backgroundColor: isUser ? PALETTE.primary : PALETTE.neutral.gray4,
        }}
        aria-label={isUser ? '用户消息' : 'AI 回复'}
      />
      <div
        style={{
          // Bubbles with artifacts get more width to comfortably fit charts.
          maxWidth: hasArtifacts ? '92%' : '78%',
          minWidth: 0,
        }}
      >
        <div
          style={{
            backgroundColor: isUser ? userBg : assistantBg,
            color: isUser ? userColor : assistantColor,
            padding: `${SPACING.sm}px ${SPACING.md}px`,
            borderRadius: GEOMETRY.borderRadiusLg,
            // Slightly square the corner nearest the avatar for a chat look.
            borderTopRightRadius: isUser ? GEOMETRY.borderRadius / 2 : GEOMETRY.borderRadiusLg,
            borderTopLeftRadius: isUser ? GEOMETRY.borderRadiusLg : GEOMETRY.borderRadius / 2,
            wordBreak: 'break-word',
            whiteSpace: 'pre-wrap',
          }}
        >
          {message.pending ? (
            <Space size={SPACING.sm}>
              <Spin size="small" />
              <Text style={{ color: assistantColor }}>正在思考…</Text>
            </Space>
          ) : (
            <Text style={{ color: isUser ? userColor : assistantColor }}>{message.content}</Text>
          )}
        </div>

        {/* Inline artifacts for assistant messages (Req 9.10-9.12). */}
        {!message.pending && hasArtifacts ? (
          <Space
            direction="vertical"
            size={SPACING.sm}
            style={{ width: '100%', marginTop: SPACING.sm }}
          >
            {message.charts.map((chart) => (
              <ChartCard key={chart.id} chart={chart} height={260} />
            ))}
            <InlineAnalysisResults results={message.analysisResults} />
          </Space>
        ) : null}
      </div>
    </div>
  );
}

export default MessageBubble;
