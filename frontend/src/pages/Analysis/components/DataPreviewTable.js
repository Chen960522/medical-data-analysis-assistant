import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Data preview table.
 *
 * Renders the first 10 rows of a parsed data file in an Ant Design `Table`
 * (Req 2.2). Columns are derived from `DataPreviewResponse.columns` and cell
 * values are coerced to a readable string, with missing/empty values shown as a
 * muted placeholder so data gaps are visible.
 */
import { Table, Tag, Typography } from 'antd';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
/** Coerce an arbitrary cell value into a display string. */
function renderCell(value) {
    if (value === null || value === undefined || value === '') {
        return _jsx(Text, { type: "secondary", children: "\u2014" });
    }
    if (typeof value === 'object') {
        return _jsx(Text, { children: JSON.stringify(value) });
    }
    return _jsx(Text, { children: String(value) });
}
export function DataPreviewTable({ preview }) {
    const columns = preview.columns.map((name) => ({
        title: name,
        dataIndex: name,
        key: name,
        ellipsis: true,
        render: (value) => renderCell(value),
    }));
    // Stable row keys: prefer an `id`-like column if present, else the index.
    const dataSource = preview.rows.map((row, index) => ({ ...row, __rowKey: index }));
    return (_jsxs("div", { children: [_jsxs(Text, { type: "secondary", style: { display: 'block', marginBottom: SPACING.sm }, children: ["\u5171 ", preview.total_rows, " \u884C \u00B7 ", preview.total_columns, " \u5217\uFF0C\u4E0B\u8868\u5C55\u793A\u524D ", preview.rows.length, " \u884C", _jsx(Tag, { style: { marginInlineStart: SPACING.sm }, children: "\u6570\u636E\u9884\u89C8" })] }), _jsx(Table, { size: "small", columns: columns, dataSource: dataSource, rowKey: "__rowKey", pagination: false, scroll: { x: 'max-content' }, bordered: true })] }));
}
export default DataPreviewTable;
