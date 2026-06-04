/**
 * Status tag.
 *
 * Renders a color-coded status indicator that also includes an icon and a text
 * label, so meaning is never conveyed by color alone (Req 12.34).
 */

import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';

export type StatusKind = 'success' | 'error' | 'processing' | 'pending' | 'warning';

const STATUS_CONFIG: Record<StatusKind, { color: string; icon: ReactNode }> = {
  success: { color: 'success', icon: <CheckCircleOutlined /> },
  error: { color: 'error', icon: <CloseCircleOutlined /> },
  processing: { color: 'processing', icon: <SyncOutlined spin /> },
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  warning: { color: 'warning', icon: <ClockCircleOutlined /> },
};

export interface StatusTagProps {
  kind: StatusKind;
  /** Visible text label (required so color is never the sole signal). */
  label: string;
}

export function StatusTag({ kind, label }: StatusTagProps) {
  const config = STATUS_CONFIG[kind];
  return (
    <Tag color={config.color} icon={config.icon}>
      {label}
    </Tag>
  );
}

export default StatusTag;
