import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { formatFileSize } from '../../../components/Upload/FileUpload';
import { StatusTag } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
import { languageLabel } from '../../../types/translation';
const { Text } = Typography;
/** Map a backend status string to a StatusTag kind + label. */
function statusDisplay(status) {
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
function formatDate(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
/** Render the translation direction, e.g. 英文 → 中文 (Req 11.43). */
function direction(source, target) {
    if (!source || !target) {
        return '—';
    }
    return `${languageLabel(source)} → ${languageLabel(target)}`;
}
export function HistoryList({ records, loading, deletingId, onOpen, onDelete, }) {
    const columns = [
        {
            title: '文件名',
            dataIndex: 'original_filename',
            key: 'original_filename',
            ellipsis: true,
            render: (value) => _jsx(Text, { children: value }),
        },
        {
            title: '大小',
            dataIndex: 'file_size',
            key: 'file_size',
            width: 110,
            render: (value) => formatFileSize(value),
        },
        {
            title: '页数',
            dataIndex: 'page_count',
            key: 'page_count',
            width: 80,
            render: (value) => (value ?? '—'),
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
            render: (value) => {
                const { kind, label } = statusDisplay(value);
                return _jsx(StatusTag, { kind: kind, label: label });
            },
        },
        {
            title: '上传时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 180,
            render: (value) => formatDate(value),
        },
        {
            title: '完成时间',
            dataIndex: 'completed_at',
            key: 'completed_at',
            width: 180,
            render: (value) => formatDate(value),
        },
        {
            title: '操作',
            key: 'actions',
            width: 180,
            render: (_, record) => (_jsxs(Space, { size: SPACING.xs, children: [_jsx(Button, { size: "small", icon: _jsx(EyeOutlined, {}), disabled: record.status !== 'completed', onClick: () => onOpen(record), children: "\u67E5\u770B" }), _jsx(Button, { size: "small", danger: true, icon: _jsx(DeleteOutlined, {}), loading: deletingId === record.id, onClick: () => onDelete(record), children: "\u5220\u9664" })] })),
        },
    ];
    return (_jsx(Table, { rowKey: "id", columns: columns, dataSource: records, loading: loading, pagination: { pageSize: 10, hideOnSinglePage: true }, scroll: { x: 960 }, locale: { emptyText: '暂无翻译历史记录' } }));
}
export default HistoryList;
