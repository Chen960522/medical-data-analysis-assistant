/**
 * Chart TypeScript types.
 *
 * Defines the supported visualization chart types (Req 4.2) and a `ChartData`
 * interface mirroring the backend `ChartResponse` schema
 * (`backend/app/schemas/analysis.py`), where each chart is delivered as a
 * ready-to-render ECharts `option` object (Req 4.1-4.6).
 */

import type { EChartsOption } from 'echarts-for-react';

/**
 * The seven chart types supported by the Chart_Generator (Req 4.2).
 * These are produced by the chart-generation MCP as ECharts options.
 */
export type ChartType =
  | 'bar'
  | 'line'
  | 'scatter'
  | 'pie'
  | 'histogram'
  | 'boxplot'
  | 'heatmap';

/** The full set of supported chart types, useful for iteration/validation. */
export const CHART_TYPES: readonly ChartType[] = [
  'bar',
  'line',
  'scatter',
  'pie',
  'histogram',
  'boxplot',
  'heatmap',
] as const;

/** Human-readable Chinese labels for each chart type. */
export const CHART_TYPE_LABELS: Record<ChartType, string> = {
  bar: '柱状图',
  line: '折线图',
  scatter: '散点图',
  pie: '饼图',
  histogram: '直方图',
  boxplot: '箱线图',
  heatmap: '热力图',
};

/** Narrowing helper: is the given string one of the supported chart types? */
export function isChartType(value: string): value is ChartType {
  return (CHART_TYPES as readonly string[]).includes(value);
}

/**
 * A single chart as delivered by the backend.
 *
 * Mirrors `ChartResponse` in `backend/app/schemas/analysis.py`:
 * - `id`: chart identifier (UUID string)
 * - `chart_type`: one of the supported {@link ChartType} values
 * - `title`: human-readable chart title
 * - `echarts_option`: a ready-to-render ECharts `option` object
 */
export interface ChartData {
  id: string;
  chart_type: ChartType | string;
  title: string;
  echarts_option: EChartsOption;
}
