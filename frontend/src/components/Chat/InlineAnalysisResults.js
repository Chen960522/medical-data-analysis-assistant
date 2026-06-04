import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Inline analysis results renderer.
 *
 * Renders the raw `analysis_results` payloads carried by an assistant message
 * compactly within the conversation (Req 9.10). The payload shapes are
 * arbitrary (the Agent may return `{ result_type, result_data }` objects or
 * free-form dicts), so values are rendered robustly:
 * - objects → a key/value `Descriptions`
 * - arrays of objects → a `Table`
 * - arrays of primitives → a `List`
 * - primitives → text
 *
 * Known `result_type` values are mapped to Chinese section titles, with a
 * fallback to the raw type (Req 3.1-3.5).
 */
import { Descriptions, List, Space, Table, Typography } from 'antd';
import { SPACING } from '../../theme/tokens';
const { Text } = Typography;
/** Known result types mapped to Chinese section titles (Req 3.1-3.5). */
const RESULT_TYPE_LABELS = {
    descriptive: '描述性统计',
    correlation: '相关性分析',
    outlier: '异常值检测',
    trend: '趋势分析',
    group_comparison: '分组比较',
};
function isPlainObject(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function primitiveToString(value) {
    if (value === null || value === undefined || value === '') {
        return '—';
    }
    if (typeof value === 'number') {
        return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, '');
    }
    if (typeof value === 'boolean') {
        return value ? '是' : '否';
    }
    return String(value);
}
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
    return (_jsx(List, { size: "small", dataSource: items, renderItem: (item) => _jsx(List.Item, { children: renderValue(item) }) }));
}
function renderObject(obj) {
    const entries = Object.entries(obj);
    if (entries.length === 0) {
        return _jsx(Text, { type: "secondary", children: "\u2014" });
    }
    return (_jsx(Descriptions, { column: 1, size: "small", bordered: true, children: entries.map(([key, value]) => (_jsx(Descriptions.Item, { label: key, children: renderValue(value) }, key))) }));
}
/** Resolve the section title and body for a single result payload. */
function resolveResult(result) {
    const resultType = typeof result.result_type === 'string' ? result.result_type : null;
    const title = resultType ? (RESULT_TYPE_LABELS[resultType] ?? resultType) : null;
    // Prefer a nested `result_data` payload when present; otherwise render the
    // whole object minus the type discriminator.
    if ('result_data' in result) {
        return { title, body: result.result_data };
    }
    if (resultType) {
        const { result_type: _omit, ...rest } = result;
        return { title, body: rest };
    }
    return { title: null, body: result };
}
export function InlineAnalysisResults({ results }) {
    if (results.length === 0) {
        return null;
    }
    return (_jsx(Space, { direction: "vertical", size: SPACING.sm, style: { width: '100%' }, children: results.map((result, index) => {
            const { title, body } = resolveResult(result);
            return (_jsxs("div", { children: [title ? (_jsx(Text, { strong: true, style: { display: 'block', marginBottom: SPACING.xs }, children: title })) : null, renderValue(body)] }, index));
        }) }));
}
export default InlineAnalysisResults;
