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
import type { AnalysisStatusResponse } from '../../../types/analysis';

const { Text } = Typography;

export interface AnalysisProgressProps {
  /** Concrete status from the backend, if available. */
  status?: AnalysisStatusResponse | null;
}

export function AnalysisProgress({ status }: AnalysisProgressProps) {
  const stage = status?.stage ?? '分析进行中';
  // Without a concrete status the request is in flight; show an active bar that
  // does not imply completion.
  const percent = status?.progress ?? 30;
  const isFailed = status?.status === 'failed';

  return (
    <Card variant="outlined" aria-live="polite">
      <Space direction="vertical" style={{ width: '100%' }} size={SPACING.sm}>
        <LoadingIndicator tip={stage} size="default" style={{ padding: SPACING.md }} />
        <div>
          <Text type="secondary">当前阶段：{stage}</Text>
          <Progress
            percent={percent}
            status={isFailed ? 'exception' : 'active'}
            aria-label={`分析进度 ${percent}%`}
          />
        </div>
      </Space>
    </Card>
  );
}

export default AnalysisProgress;
