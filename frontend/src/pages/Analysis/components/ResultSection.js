import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Analysis result section.
 *
 * Renders a single {@link AnalysisResult} as a titled card. The `result_type`
 * is mapped to a Chinese section title (descriptive statistics, correlation,
 * outliers, trend, group comparison) with a fallback to the raw type
 * (Req 3.1-3.5). The arbitrary `result_data` payload is rendered robustly:
 * - objects → a key/value `Descriptions`
 * - arrays of objects → a `Table`
 * - arrays of primitives → a `List`
 * - primitives → text
 *
 * Nested values are rendered recursively so deep result shapes stay readable.
 */
import { Card, Descriptions, List, Table, Typography } from 'antd';
import { SPACING } from '../../../theme/tokens';
const { Text, Paragraph } = Typography;
/** Known result types mapped to Chinese section titles (Req 3.1-3.5). */
export const RESULT_TYPE_LABELS = {
    descriptive: '描述性统计',
    correlation: '相关性分析',
    outlier: '异常值检测',
    trend: '趋势分析',
    group_comparison: '分组比较',
};
/** Resolve a result type to its Chinese section title, falling back to the raw type. */
export function resultTypeLabel(resultType) {
    return RESULT_TYPE_LABELS[resultType] ?? resultType;
}
function isPlainObject(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function primitiveToString(value) {
    if (value === null || value === undefined || value === '') {
        return '—';
    }
    if (typeof value === 'number') {
        // Trim long floats for readability.
        return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, '');
    }
    return String(value);
}
/** Recursively render an arbitrary value into a React node. */
function renderValue(value) {
    if (Array.isArray(value)) {
        return renderArray(value);
    }
    if (isPlainObject(value)) {
        return renderObject(value);
    }
    return _jsx(Text, { children: primitiveToString(value) });
}
function renderArray(items) {
    if (items.length === 0) {
        return _jsx(Text, { type: "secondary", children: "\u2014" });
    }
    // Array of homogeneous objects → table with a union of keys as columns.
    if (items.every((item) => isPlainObject(item))) {
        const records = items;
        const keys = Array.from(records.reduce((set, record) => {
            Object.keys(record).forEach((key) => set.add(key));
            return set;
        }, new Set()));
        const columns = keys.map((key) => ({
            title: key,
            dataIndex: key,
            key,
            render: (cell) => renderValue(cell),
        }));
        const dataSource = records.map((record, index) => ({ ...record, __rowKey: index }));
        return (_jsx(Table, { size: "small", columns: columns, dataSource: dataSource, rowKey: "__rowKey", pagination: false, scroll: { x: 'max-content' }, bordered: true }));
    }
    // Array of primitives (or mixed) → list.
    return (_jsx(List, { size: "small", dataSource: items, renderItem: (item) => _jsx(List.Item, { children: renderValue(item) }) }));
}
function renderObject(obj) {
    const entries = Object.entries(obj);
    if (entries.length === 0) {
        return _jsx(Text, { type: "secondary", children: "\u2014" });
    }
    return (_jsx(Descriptions, { column: 1, size: "small", bordered: true, children: entries.map(([key, value]) => (_jsx(Descriptions.Item, { label: key, children: renderValue(value) }, key))) }));
}
export function ResultSection({ result }) {
    const title = resultTypeLabel(result.result_type);
    const data = result.result_data;
    const hasData = data && Object.keys(data).length > 0;
    return (_jsx(Card, { title: title, variant: "outlined", style: { marginBottom: SPACING.md }, styles: { body: { paddingBlock: SPACING.md } }, children: hasData ? (renderValue(data)) : (_jsx(Paragraph, { type: "secondary", style: { marginBottom: 0 }, children: "\u6682\u65E0\u8BE5\u7EF4\u5EA6\u7684\u8BE6\u7EC6\u6570\u636E\u3002" })) }));
}
export default ResultSection;
