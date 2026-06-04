/**
 * Client-side ECharts option builders.
 *
 * The platform primarily renders ready-made ECharts options produced by the
 * chart-generation MCP (Req 4.1-4.6). These builders provide minimal, correct
 * option construction for each of the seven supported chart types (Req 4.2)
 * from simple inputs, supporting local rendering, demos, and any future
 * client-side charting. They intentionally produce only the chart-specific
 * configuration; unified styling (palette, tooltip, grid, fonts) is layered on
 * separately via `applyChartTheme`.
 */

import type { EChartsOption } from 'echarts-for-react';

import type { ChartType } from './ChartTypes';

/** A simple {category, value} pair used by categorical charts. */
export interface CategoryValue {
  name: string;
  value: number;
}

/** Build a bar chart option (Req 4.2, 4.5). */
export function buildBarChart(
  categories: string[],
  values: number[],
  title = '',
): EChartsOption {
  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'category', data: categories },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: values }],
  };
}

/** Build a line chart option for trends over time (Req 4.2, 4.4). */
export function buildLineChart(
  categories: string[],
  values: number[],
  title = '',
): EChartsOption {
  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'category', boundaryGap: false, data: categories },
    yAxis: { type: 'value' },
    series: [{ type: 'line', smooth: true, data: values }],
  };
}

/** Build a scatter plot option for correlations (Req 4.2, 4.6). */
export function buildScatterChart(
  points: Array<[number, number]>,
  title = '',
): EChartsOption {
  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'value', scale: true },
    yAxis: { type: 'value', scale: true },
    series: [{ type: 'scatter', data: points.map((p) => [p[0], p[1]]) }],
  };
}

/** Build a pie chart option for group comparisons (Req 4.2, 4.5). */
export function buildPieChart(data: CategoryValue[], title = ''): EChartsOption {
  return {
    title: title ? { text: title } : undefined,
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: data.map((d) => ({ name: d.name, value: d.value })),
      },
    ],
  };
}

/**
 * Build a histogram option from raw numeric samples (Req 4.2, 4.3).
 *
 * Bins the values into `binCount` equal-width buckets and renders them as a
 * contiguous bar series (no inter-bar gap) labelled by bucket range.
 */
export function buildHistogram(
  values: number[],
  binCount = 10,
  title = '',
): EChartsOption {
  const bins = Math.max(1, Math.floor(binCount));
  if (values.length === 0) {
    return {
      title: title ? { text: title } : undefined,
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', barWidth: '99%', data: [] }],
    };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  const width = range === 0 ? 1 : range / bins;
  const counts = new Array<number>(bins).fill(0);

  for (const value of values) {
    let index = range === 0 ? 0 : Math.floor((value - min) / width);
    if (index >= bins) {
      index = bins - 1; // include the max value in the last bin
    }
    if (index < 0) {
      index = 0;
    }
    counts[index] = (counts[index] ?? 0) + 1;
  }

  const labels = counts.map((_, i) => {
    const start = min + i * width;
    const end = start + width;
    return `${start.toFixed(1)}~${end.toFixed(1)}`;
  });

  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', barWidth: '99%', data: counts }],
  };
}

/** Five-number summary for a box plot: [min, Q1, median, Q3, max]. */
export type BoxplotSummary = [number, number, number, number, number];

/** Compute a linear-interpolated quantile from sorted ascending values. */
function quantileSorted(sorted: number[], q: number): number {
  if (sorted.length === 0) {
    return 0;
  }
  if (sorted.length === 1) {
    return sorted[0] as number;
  }
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const lower = sorted[base] as number;
  const upper = sorted[base + 1] ?? lower;
  return lower + rest * (upper - lower);
}

/** Compute the [min, Q1, median, Q3, max] summary for a series of numbers. */
export function computeBoxplotSummary(values: number[]): BoxplotSummary {
  if (values.length === 0) {
    return [0, 0, 0, 0, 0];
  }
  const sorted = [...values].sort((a, b) => a - b);
  return [
    sorted[0] as number,
    quantileSorted(sorted, 0.25),
    quantileSorted(sorted, 0.5),
    quantileSorted(sorted, 0.75),
    sorted[sorted.length - 1] as number,
  ];
}

/**
 * Build a box plot option from grouped numeric samples (Req 4.2, 4.3).
 *
 * `groups` maps each category name to its raw numeric samples; the five-number
 * summary is computed per group.
 */
export function buildBoxplot(
  groups: Record<string, number[]>,
  title = '',
): EChartsOption {
  const names = Object.keys(groups);
  const data = names.map((name) => computeBoxplotSummary(groups[name] ?? []));
  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value' },
    series: [{ type: 'boxplot', data }],
  };
}

/**
 * Build a heatmap option (Req 4.2, 4.6).
 *
 * `matrix[y][x]` holds the value at column `x`, row `y`. A `visualMap` is added
 * so the value scale is legible.
 */
export function buildHeatmap(
  xLabels: string[],
  yLabels: string[],
  matrix: number[][],
  title = '',
): EChartsOption {
  const data: Array<[number, number, number]> = [];
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (let y = 0; y < yLabels.length; y += 1) {
    const row = matrix[y] ?? [];
    for (let x = 0; x < xLabels.length; x += 1) {
      const value = row[x] ?? 0;
      data.push([x, y, value]);
      if (value < min) min = value;
      if (value > max) max = value;
    }
  }
  if (!Number.isFinite(min)) min = 0;
  if (!Number.isFinite(max)) max = 0;

  return {
    title: title ? { text: title } : undefined,
    xAxis: { type: 'category', data: xLabels },
    yAxis: { type: 'category', data: yLabels },
    visualMap: {
      min,
      max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [{ type: 'heatmap', data, label: { show: false } }],
  };
}

/** A discriminated set of inputs accepted by {@link buildChart}. */
export type ChartBuilderInput =
  | { type: 'bar'; categories: string[]; values: number[]; title?: string }
  | { type: 'line'; categories: string[]; values: number[]; title?: string }
  | { type: 'scatter'; points: Array<[number, number]>; title?: string }
  | { type: 'pie'; data: CategoryValue[]; title?: string }
  | { type: 'histogram'; values: number[]; binCount?: number; title?: string }
  | { type: 'boxplot'; groups: Record<string, number[]>; title?: string }
  | {
      type: 'heatmap';
      xLabels: string[];
      yLabels: string[];
      matrix: number[][];
      title?: string;
    };

/** Build a chart option for any supported {@link ChartType} from simple input. */
export function buildChart(input: ChartBuilderInput): EChartsOption {
  switch (input.type) {
    case 'bar':
      return buildBarChart(input.categories, input.values, input.title);
    case 'line':
      return buildLineChart(input.categories, input.values, input.title);
    case 'scatter':
      return buildScatterChart(input.points, input.title);
    case 'pie':
      return buildPieChart(input.data, input.title);
    case 'histogram':
      return buildHistogram(input.values, input.binCount, input.title);
    case 'boxplot':
      return buildBoxplot(input.groups, input.title);
    case 'heatmap':
      return buildHeatmap(input.xLabels, input.yLabels, input.matrix, input.title);
    default: {
      // Exhaustiveness guard: every ChartType must be handled above.
      const _exhaustive: never = input;
      return _exhaustive;
    }
  }
}

/** Re-exported for convenience so callers can reference the union directly. */
export type { ChartType };
