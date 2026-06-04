/**
 * Translation history list (Req 11.43-11.47).
 *
 * Lists the user's translation records (newest first, provided by the caller)
 * showing file name, size, page count, source/target language, status, and
 * dates. Allows opening a past translation (Req 11.45) and deleting a record
 * with a confirmation dialog (Req 11.46), wired through callbacks.
 */

import { Button, Space, Table, Typography } from 'antd';
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import { formatFileSize } from '../../../components/Upload/FileUpload';
import { StatusTag } from '../../../components/Common';
import type { StatusKind } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
import { languageLabel } from '../../../types/translation';
import type { LanguageCode, TranslationHistoryItem } from '../../../types/translation';

const { Text } = Typography;

export interface HistoryListProps {
  records: TranslationHistoryItem[];
  loading: boolean;
  /** Id of the record currently being deleted (disables its actions). */
  deletingId?: string | null;
  onOpen: (record: TranslationHistoryItem) => void;
  onDelete: (record: TranslationHistoryItem) => void;
}

/** Map a backend status string to a StatusTag kind + label. */
function statusDisplay(status: string): { kind: StatusKind; label: string } {
  switch (status) {
    case 'completed':
      return { kind: 'success', label: '已完成' };
    case 'processing':
      return { kind: 'processing', label: '翻译中' };
    case 'failed':
      return { kind: 'error', label: '失败' };
    case 'uploaded':
      return { kind: 'pending', label: '待翻译' };
    default:
      return { kind: 'pending', label: status };
  }
}

/** Format an ISO timestamp into a locale string (blank when absent). */
function formatDate(value?: string | null): string {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/** Render the translation direction, e.g. 英文 → 中文 (Req 11.43). */
function direction(source?: LanguageCode | null, target?: LanguageCode | null): string {
  if (!source || !target) {
    return '—';
  }
  return `${languageLabel(source)} → ${languageLabel(target)}`;
}

export function HistoryList({
  records,
  loading,
  deletingId,
  onOpen,
  onDelete,
}: HistoryListProps) {
  const columns: ColumnsType<TranslationHistoryItem> = [
    {
      title: '文件名',
      dataIndex: 'original_filename',
      key: 'original_filename',
      ellipsis: true,
      render: (value: string) => <Text>{value}</Text>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 110,
      render: (value: number) => formatFileSize(value),
    },
    {
      title: '页数',
      dataIndex: 'page_count',
      key: 'page_count',
      width: 80,
      render: (value?: number | null) => (value ?? '—'),
    },
    {
      title: '翻译方向',
      key: 'direction',
      width: 140,
      render: (_, record) => direction(record.source_language, record.target_language),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => {
        const { kind, label } = statusDisplay(value);
        return <StatusTag kind={kind} label={label} />;
      },
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string) => formatDate(value),
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 180,
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
    <Table<TranslationHistoryItem>
      rowKey="id"
      columns={columns}
      dataSource={records}
      loading={loading}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      scroll={{ x: 960 }}
      locale={{ emptyText: '暂无翻译历史记录' }}
    />
  );
}

export default HistoryList;
