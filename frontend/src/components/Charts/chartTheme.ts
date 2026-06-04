/**
 * Unified chart theming.
 *
 * Provides a coordinated medical color palette and base ECharts styling so that
 * every chart in an analysis session shares a harmonious visual language
 * (Req 4 unified styling, Req 12.22 coordinated palette, Req 12.23 self-
 * explanatory axes/legends/titles, Req 12.24 smooth/anti-aliased rendering with
 * consistent fonts).
 *
 * `applyChartTheme` merges base styling (color palette, tooltip, grid, font)
 * into a given ECharts option without clobbering chart-specific configuration,
 * and ensures hover tooltips (Req 4.7) plus zoom/filter affordances
 * (`dataZoom`/`toolbox`) where appropriate (Req 4.7).
 */

import type { EChartsOption } from 'echarts-for-react';

import { PALETTE, TYPOGRAPHY } from '../../theme/tokens';
import type { ChartType } from './ChartTypes';

/**
 * Coordinated categorical color palette for series, derived from the medical
 * blue primary and complementary hues. Applied across all charts in a session
 * to maintain visual harmony (Req 12.22).
 */
export const CHART_COLOR_PALETTE: readonly string[] = [
  PALETTE.primary, // medical blue
  '#13c2c2', // teal
  '#52c41a', // green
  '#faad14', // amber
  '#722ed1', // violet
  '#eb2f96', // magenta
  '#fa8c16', // orange
  '#2f54eb', // indigo
  '#a0d911', // lime
  '#f5222d', // red (used sparingly, Req 12.3)
] as const;

/**
 * Sequential palette for continuous visual mappings (e.g. heatmap), running
 * from a light tint to the medical blue primary.
 */
export const CHART_SEQUENTIAL_PALETTE: readonly string[] = [
  '#e6f0ff',
  '#bae0ff',
  '#91caff',
  '#69b1ff',
  '#4096ff',
  PALETTE.primary,
  PALETTE.primaryActive,
] as const;

/** Resolved styling values for a given theme mode. */
export interface ChartThemeColors {
  /** Container/canvas background color. */
  background: string;
  /** Primary text color (titles, labels). */
  text: string;
  /** Secondary/axis text color. */
  textSecondary: string;
  /** Axis line / split line color. */
  axisLine: string;
  /** Split (grid) line color. */
  splitLine: string;
  /** Tooltip background color. */
  tooltipBg: string;
}

/** Resolve theme-dependent chart colors for light/dark modes (Req 12.29). */
export function getChartThemeColors(mode: 'light' | 'dark'): ChartThemeColors {
  if (mode === 'dark') {
    return {
      background: 'transparent',
      text: PALETTE.neutral.gray1,
      textSecondary: PALETTE.neutral.gray4,
      axisLine: PALETTE.neutral.gray6,
      splitLine: PALETTE.neutral.gray7,
      tooltipBg: PALETTE.neutral.gray7,
    };
  }
  return {
    background: 'transparent',
    text: PALETTE.neutral.gray8,
    textSecondary: PALETTE.neutral.gray5,
    axisLine: PALETTE.neutral.gray3,
    splitLine: PALETTE.neutral.gray2,
    tooltipBg: PALETTE.neutral.white,
  };
}

type PlainObject = Record<string, unknown>;

function isPlainObject(value: unknown): value is PlainObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Deep-merge `source` defaults into `target` without clobbering values the
 * caller (the backend option) already supplied. Existing keys on `target`
 * always win; only missing keys are filled in from `source`.
 */
function mergeDefaults<T>(target: T, source: PlainObject): T {
  if (!isPlainObject(target)) {
    return target;
  }
  const result: PlainObject = { ...target };
  for (const [key, sourceValue] of Object.entries(source)) {
    const targetValue = result[key];
    if (targetValue === undefined) {
      result[key] = sourceValue;
    } else if (isPlainObject(targetValue) && isPlainObject(sourceValue)) {
      result[key] = mergeDefaults(targetValue, sourceValue);
    }
    // Otherwise keep the caller-provided value (arrays, primitives) untouched.
  }
  return result as T;
}

export interface ApplyChartThemeOptions {
  /** Active theme mode; controls text/grid/background colors (Req 12.29). */
  mode?: 'light' | 'dark';
  /**
   * The chart type, used to decide whether to add zoom/filter affordances.
   * Cartesian charts (bar/line/scatter/histogram/boxplot) benefit from
   * `dataZoom`; pie/heatmap do not.
   */
  chartType?: ChartType | string;
  /** When false, do not inject `dataZoom`/`toolbox`. Defaults to true. */
  enableZoom?: boolean;
}

/** Chart types that sit on a cartesian grid and support zoom/filter. */
const CARTESIAN_TYPES = new Set<string>(['bar', 'line', 'scatter', 'histogram', 'boxplot']);

/**
 * Merge unified base styling into an ECharts option.
 *
 * The returned option preserves all chart-specific configuration provided by
 * the caller and only fills in styling defaults (color palette, font, tooltip,
 * grid, axis colors) plus interaction affordances where appropriate.
 */
export function applyChartTheme(
  option: EChartsOption,
  { mode = 'light', chartType, enableZoom = true }: ApplyChartThemeOptions = {},
): EChartsOption {
  const colors = getChartThemeColors(mode);
  const base: PlainObject = {
    // Coordinated categorical palette (Req 12.22).
    color: [...CHART_COLOR_PALETTE],
    backgroundColor: colors.background,
    textStyle: {
      fontFamily: TYPOGRAPHY.fontFamily,
      fontSize: TYPOGRAPHY.bodySizes.base,
      color: colors.text,
    },
    // Hover-for-detail tooltips (Req 4.7).
    tooltip: {
      trigger: CARTESIAN_TYPES.has(String(chartType)) ? 'axis' : 'item',
      backgroundColor: colors.tooltipBg,
      borderColor: colors.axisLine,
      textStyle: { color: colors.text, fontFamily: TYPOGRAPHY.fontFamily },
    },
    // Whitespace-conscious title styling (Req 12.23).
    title: {
      textStyle: { color: colors.text, fontFamily: TYPOGRAPHY.fontFamily },
      left: 'center',
    },
    legend: {
      textStyle: { color: colors.textSecondary, fontFamily: TYPOGRAPHY.fontFamily },
    },
    grid: {
      containLabel: true,
      left: '5%',
      right: '5%',
      bottom: '8%',
      top: 56,
    },
  };

  const isCartesian = CARTESIAN_TYPES.has(String(chartType));
  if (isCartesian) {
    // Axis defaults for self-explanatory, smoothly rendered charts
    // (Req 12.23, 12.24).
    base.xAxis = {
      axisLine: { lineStyle: { color: colors.axisLine } },
      axisLabel: { color: colors.textSecondary },
      splitLine: { lineStyle: { color: colors.splitLine } },
    };
    base.yAxis = {
      axisLine: { lineStyle: { color: colors.axisLine } },
      axisLabel: { color: colors.textSecondary },
      splitLine: { lineStyle: { color: colors.splitLine } },
    };

    if (enableZoom) {
      // Zoom + filter affordances (Req 4.7): an inside (scroll/pinch) zoom plus
      // a slider, and a toolbox with restore/data-view controls.
      base.dataZoom = [
        { type: 'inside' },
        { type: 'slider', bottom: 8 },
      ];
      base.toolbox = {
        right: 16,
        feature: {
          dataZoom: { yAxisIndex: 'none', title: { zoom: '区域缩放', back: '还原缩放' } },
          restore: { title: '重置' },
          dataView: { readOnly: true, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] },
        },
      };
    }
  }

  return mergeDefaults(option, base);
}
