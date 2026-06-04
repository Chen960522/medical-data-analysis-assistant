/**
 * Analysis history list (Req 6.1-6.5).
 *
 * Lists the authenticated user's analysis sessions (sorted by date descending,
 * provided by the caller per Req 6.2) showing a short id, status, and the
 * created/completed timestamps. Allows opening a completed analysis to view its
 * full results, charts, and report (Req 6.3) and deleting a record with a
 * confirmation dialog handled by the caller (Req 6.4), wired through callbacks.
 */

import { Button, Space, Table, Typography } from 'antd';
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import { StatusTag } from '../../../components/Common';
import type { StatusKind } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
import type { AnalysisSession, AnalysisStatus } from '../../../types/analysis';

const { Text } = Typography;

export interface AnalysisHistoryListProps {
  sessions: AnalysisSession[];
  loading: boolean;
  /** Id of the record currently being deleted (disables/loads its delete action). */
  deletingId?: string | null;
  onOpen: (session: AnalysisSession) => void;
  onDelete: (session: AnalysisSession) => void;
}

/** Map a backend analysis status to a StatusTag kind + label (Req 3.7). */
function statusDisplay(status: AnalysisStatus): { kind: StatusKind; label: string } {
  switch (status) {
    case 'completed':
      return { kind: 'success', label: '已完成' };
    case 'running':
      return { kind: 'processing', label: '分析中' };
    case 'pending':
      return { kind: 'pending', label: '等待中' };
    case 'failed':
      return { kind: 'error', label: '失败' };
    default:
      return { kind: 'pending', label: status };
  }
}

/** Format an ISO timestamp into a locale string (em dash when absent). */
function formatDate(value?: string | null): string {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function AnalysisHistoryList({
  sessions,
  loading,
  deletingId,
  onOpen,
  onDelete,
}: AnalysisHistoryListProps) {
  const columns: ColumnsType<AnalysisSession> = [
    {
      title: '分析编号',
      dataIndex: 'id',
      key: 'id',
      ellipsis: true,
      render: (value: string) => <Text code>{value.slice(0, 8)}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: AnalysisStatus) => {
        const { kind, label } = statusDisplay(value);
        return <StatusTag kind={kind} label={label} />;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => formatDate(value),
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 200,
      render: (value?: string | null) => formatDate(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_, record) => (
        <Space size={SPACING.xs}>
          <Button
            size="small"
            icon={<EyeOutlined />}
            disabled={record.status !== 'completed'}
            onClick={() => onOpen(record)}
          >
            查看
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            loading={deletingId === record.id}
            onClick={() => onDelete(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table<AnalysisSession>
      rowKey="id"
      columns={columns}
      dataSource={sessions}
      loading={loading}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      scroll={{ x: 820 }}
      locale={{ emptyText: '暂无分析历史记录' }}
    />
  );
}

export default AnalysisHistoryList;
