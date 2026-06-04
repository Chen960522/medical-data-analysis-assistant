import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { StatusTag } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
/** Map a backend analysis status to a StatusTag kind + label (Req 3.7). */
function statusDisplay(status) {
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
function formatDate(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
export function AnalysisHistoryList({ sessions, loading, deletingId, onOpen, onDelete, }) {
    const columns = [
        {
            title: '分析编号',
            dataIndex: 'id',
            key: 'id',
            ellipsis: true,
            render: (value) => _jsx(Text, { code: true, children: value.slice(0, 8) }),
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            width: 120,
            render: (value) => {
                const { kind, label } = statusDisplay(value);
                return _jsx(StatusTag, { kind: kind, label: label });
            },
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 200,
            render: (value) => formatDate(value),
        },
        {
            title: '完成时间',
            dataIndex: 'completed_at',
            key: 'completed_at',
            width: 200,
            render: (value) => formatDate(value),
        },
        {
            title: '操作',
            key: 'actions',
            width: 180,
            render: (_, record) => (_jsxs(Space, { size: SPACING.xs, children: [_jsx(Button, { size: "small", icon: _jsx(EyeOutlined, {}), disabled: record.status !== 'completed', onClick: () => onOpen(record), children: "\u67E5\u770B" }), _jsx(Button, { size: "small", danger: true, icon: _jsx(DeleteOutlined, {}), loading: deletingId === record.id, onClick: () => onDelete(record), children: "\u5220\u9664" })] })),
        },
    ];
    return (_jsx(Table, { rowKey: "id", columns: columns, dataSource: sessions, loading: loading, pagination: { pageSize: 10, hideOnSinglePage: true }, scroll: { x: 820 }, locale: { emptyText: '暂无分析历史记录' } }));
}
export default AnalysisHistoryList;
