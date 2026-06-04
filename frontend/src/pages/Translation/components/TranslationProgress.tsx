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

export interface TranslationProgressProps {
  /** Known progress percentage (0-100), or null when indeterminate. */
  percent?: number | null;
}

export function TranslationProgress({ percent }: TranslationProgressProps) {
  // When the percentage is unknown, keep the bar active near the start so the
  // user sees ongoing activity (Req 12.14) without implying completion.
  const value = typeof percent === 'number' ? Math.min(100, Math.max(0, Math.round(percent))) : 10;

  return (
    <Space direction="vertical" size={SPACING.sm} style={{ width: '100%' }} aria-live="polite">
      <Text type="secondary">正在翻译文档，请稍候…</Text>
      <Progress percent={value} status="active" />
    </Space>
  );
}

export default TranslationProgress;
