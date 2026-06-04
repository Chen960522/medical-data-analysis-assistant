/**
 * Contextual loading indicator.
 *
 * Displays a spinner with descriptive text explaining the current operation
 * (file upload, analysis execution, translation processing, etc.) per Req 12.14.
 * The descriptive text is also exposed to assistive tech via aria-live.
 */

import { Spin, Typography } from 'antd';
import type { CSSProperties } from 'react';

import { SPACING } from '../../theme/tokens';

const { Text } = Typography;

export interface LoadingIndicatorProps {
  /** Descriptive text explaining the in-progress operation (Req 12.14). */
  tip?: string;
  /** Spinner size. */
  size?: 'small' | 'default' | 'large';
  /** When true, fills and centers within the parent container. */
  fullHeight?: boolean;
  style?: CSSProperties;
}

export function LoadingIndicator({
  tip = '加载中…',
  size = 'large',
  fullHeight = false,
  style,
}: LoadingIndicatorProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.md,
    padding: SPACING.xl,
    minHeight: fullHeight ? '60vh' : undefined,
    ...style,
  };

  return (
    <div style={containerStyle} role="status" aria-live="polite">
      <Spin size={size} />
      {tip ? <Text type="secondary">{tip}</Text> : null}
    </div>
  );
}

export default LoadingIndicator;
