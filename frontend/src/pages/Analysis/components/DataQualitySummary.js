import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Data quality summary.
 *
 * Displays a data quality report (Req 2.6): overall totals (rows, columns,
 * missing-value percentage) via `Statistic`s, and a per-column table listing
 * each column's detected dtype and missing count/percentage. Columns with
 * missing values are flagged with a warning tag so data gaps are easy to spot.
 */
import { Card, Col, Row, Statistic, Table, Tag } from 'antd';
import { PALETTE, SPACING } from '../../../theme/tokens';
/** Map a backend dtype string to a Chinese label. */
const DTYPE_LABELS = {
    numeric: '数值',
    integer: '整数',
    float: '浮点',
    categorical: '分类',
    category: '分类',
    date: '日期',
    datetime: '日期时间',
    text: '文本',
    string: '文本',
    boolean: '布尔',
    object: '文本',
};
function dtypeLabel(dtype) {
    return DTYPE_LABELS[dtype.toLowerCase()] ?? dtype;
}
export function DataQualitySummary({ quality }) {
    const columns = [
        {
            title: '列名',
            dataIndex: 'name',
            key: 'name',
            ellipsis: true,
        },
        {
            title: '检测类型',
            dataIndex: 'dtype',
            key: 'dtype',
            render: (dtype) => _jsx(Tag, { children: dtypeLabel(dtype) }),
        },
        {
            title: '缺失值数量',
            dataIndex: 'missing_count',
            key: 'missing_count',
            sorter: (a, b) => a.missing_count - b.missing_count,
        },
        {
            title: '缺失值占比',
            dataIndex: 'missing_percentage',
            key: 'missing_percentage',
            sorter: (a, b) => a.missing_percentage - b.missing_percentage,
            render: (pct) => pct > 0 ? (_jsxs(Tag, { color: "warning", children: [pct.toFixed(1), "%"] })) : (_jsx(Tag, { color: "success", children: "0%" })),
        },
    ];
    const missingPct = quality.missing_value_percentage;
    return (_jsxs("div", { children: [_jsxs(Row, { gutter: [SPACING.md, SPACING.md], style: { marginBottom: SPACING.md }, children: [_jsx(Col, { xs: 24, sm: 8, children: _jsx(Card, { variant: "outlined", children: _jsx(Statistic, { title: "\u603B\u884C\u6570", value: quality.total_rows }) }) }), _jsx(Col, { xs: 24, sm: 8, children: _jsx(Card, { variant: "outlined", children: _jsx(Statistic, { title: "\u603B\u5217\u6570", value: quality.total_columns }) }) }), _jsx(Col, { xs: 24, sm: 8, children: _jsx(Card, { variant: "outlined", children: _jsx(Statistic, { title: "\u6574\u4F53\u7F3A\u5931\u503C\u5360\u6BD4", value: missingPct, precision: 1, suffix: "%", valueStyle: { color: missingPct > 0 ? PALETTE.warning : PALETTE.success } }) }) })] }), _jsx(Table, { size: "small", columns: columns, dataSource: quality.columns, rowKey: "name", pagination: false, bordered: true, scroll: { x: 'max-content' } })] }));
}
export default DataQualitySummary;
