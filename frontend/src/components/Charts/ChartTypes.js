/**
 * Chart TypeScript types.
 *
 * Defines the supported visualization chart types (Req 4.2) and a `ChartData`
 * interface mirroring the backend `ChartResponse` schema
 * (`backend/app/schemas/analysis.py`), where each chart is delivered as a
 * ready-to-render ECharts `option` object (Req 4.1-4.6).
 */
/** The full set of supported chart types, useful for iteration/validation. */
export const CHART_TYPES = [
    'bar',
    'line',
    'scatter',
    'pie',
    'histogram',
    'boxplot',
    'heatmap',
];
/** Human-readable Chinese labels for each chart type. */
export const CHART_TYPE_LABELS = {
    bar: '柱状图',
    line: '折线图',
    scatter: '散点图',
    pie: '饼图',
    histogram: '直方图',
    boxplot: '箱线图',
    heatmap: '热力图',
};
/** Narrowing helper: is the given string one of the supported chart types? */
export function isChartType(value) {
    return CHART_TYPES.includes(value);
}
