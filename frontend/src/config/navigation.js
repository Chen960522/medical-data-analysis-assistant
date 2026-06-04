import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Primary navigation configuration.
 *
 * Defines the persistent main navigation structure giving access to all primary
 * functional modules within 2 clicks (Req 12.18). Each item carries an icon from
 * a single unified icon set (outline style, Req 12.12) and a route path used for
 * active-item highlighting (Req 12.19) and breadcrumbs (Req 12.20).
 */
import { DashboardOutlined, BarChartOutlined, BookOutlined, TranslationOutlined, HistoryOutlined, FileSyncOutlined, } from '@ant-design/icons';
export const NAV_ITEMS = [
    {
        key: 'dashboard',
        path: '/dashboard',
        label: '仪表盘',
        icon: _jsx(DashboardOutlined, {}),
    },
    {
        key: 'analysis',
        path: '/analysis',
        label: '数据分析',
        icon: _jsx(BarChartOutlined, {}),
    },
    {
        key: 'literature',
        path: '/literature',
        label: '文献检索',
        icon: _jsx(BookOutlined, {}),
    },
    {
        key: 'translation',
        path: '/translation',
        label: 'PDF 翻译',
        icon: _jsx(TranslationOutlined, {}),
    },
    {
        key: 'history',
        path: '/history',
        label: '分析历史',
        icon: _jsx(HistoryOutlined, {}),
    },
    {
        key: 'translation-history',
        path: '/translation-history',
        label: '翻译历史',
        icon: _jsx(FileSyncOutlined, {}),
    },
];
/** Lookup map from route path to its human-readable label (for breadcrumbs). */
export const PATH_LABEL_MAP = NAV_ITEMS.reduce((acc, item) => {
    acc[item.path] = item.label;
    return acc;
}, {});
