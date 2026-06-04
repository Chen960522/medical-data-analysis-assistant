import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Literature search result list.
 *
 * Renders the merged, paginated result list (Req 10.22) with a results summary
 * showing the merged total and per-source counts (Req 10.28), sorting controls
 * (relevance / date / citations, Req 10.24), and a client-side source filter to
 * view CNKI-only / PubMed-only / both within the fetched page (Req 10.25).
 * Pagination re-fetches with the new page (default 20/page, Req 10.5).
 */
import { useMemo } from 'react';
import { Empty, List, Pagination, Segmented, Select, Space, Tag, Typography } from 'antd';
import { LoadingIndicator } from '../../../components/Common';
import { SOURCE_LABELS } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';
import { ResultItem } from './ResultItem';
const { Text } = Typography;
const SORT_OPTIONS = [
    { label: '相关性', value: 'relevance' },
    { label: '最新发表', value: 'date' },
    { label: '引用数', value: 'citations' },
];
export function ResultList({ records, keywords, loading, searched, page, pageSize, total, totals, sortBy, sourceFilter, onSortChange, onSourceFilterChange, onPageChange, onOpenDetail, onSave, }) {
    // Client-side source filter on the merged page (Req 10.25).
    const visibleRecords = useMemo(() => {
        if (sourceFilter === 'all') {
            return records;
        }
        return records.filter((record) => record.data_source === sourceFilter);
    }, [records, sourceFilter]);
    if (loading) {
        return _jsx(LoadingIndicator, { tip: "\u6B63\u5728\u68C0\u7D22\u6587\u732E\u2026" });
    }
    if (!searched) {
        return _jsx(Empty, { description: "\u8BF7\u8F93\u5165\u5173\u952E\u8BCD\u5E76\u5F00\u59CB\u641C\u7D22" });
    }
    if (total === 0) {
        return (_jsx(Empty, { description: "\u672A\u627E\u5230\u5339\u914D\u7684\u6587\u732E\uFF0C\u8BF7\u5C1D\u8BD5\u66F4\u6362\u6216\u7CBE\u7B80\u5173\u952E\u8BCD\u3001\u8C03\u6574\u6570\u636E\u6E90\u6216\u65F6\u95F4\u8303\u56F4" }));
    }
    const cnkiTotal = totals[SOURCE_LABELS.cnki] ?? 0;
    const pubmedTotal = totals[SOURCE_LABELS.pubmed] ?? 0;
    return (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsxs(Space, { size: SPACING.sm, wrap: true, children: [_jsxs(Text, { strong: true, children: ["\u5171 ", total, " \u6761\u7ED3\u679C"] }), _jsxs(Tag, { color: "volcano", children: ["CNKI ", cnkiTotal] }), _jsxs(Tag, { color: "geekblue", children: ["PubMed ", pubmedTotal] })] }), _jsxs(Space, { size: SPACING.md, wrap: true, children: [_jsxs(Space, { size: SPACING.xs, children: [_jsx(Text, { type: "secondary", children: "\u6392\u5E8F\uFF1A" }), _jsx(Select, { value: sortBy, onChange: onSortChange, options: SORT_OPTIONS, style: { width: 140 } })] }), _jsxs(Space, { size: SPACING.xs, children: [_jsx(Text, { type: "secondary", children: "\u6570\u636E\u6E90\uFF1A" }), _jsx(Segmented, { value: sourceFilter, onChange: (value) => onSourceFilterChange(value), options: [
                                    { label: '全部', value: 'all' },
                                    { label: 'CNKI', value: 'CNKI' },
                                    { label: 'PubMed', value: 'PubMed' },
                                ] })] })] }), visibleRecords.length === 0 ? (_jsx(Empty, { description: "\u5F53\u524D\u6570\u636E\u6E90\u7B5B\u9009\u4E0B\u6CA1\u6709\u7ED3\u679C" })) : (_jsx(List, { itemLayout: "vertical", dataSource: visibleRecords, rowKey: (record) => `${record.data_source}:${record.external_id ?? record.doi ?? record.title}`, renderItem: (record) => (_jsx(ResultItem, { record: record, keywords: keywords, onOpenDetail: onOpenDetail, onSave: onSave })) })), _jsx("div", { style: { textAlign: 'right' }, children: _jsx(Pagination, { current: page, pageSize: pageSize, total: total, showSizeChanger: false, onChange: onPageChange }) })] }));
}
export default ResultList;
