/** Charts component library barrel exports. */

export { EChart } from './EChart';
export type { EChartProps, EChartHandle } from './EChart';

export { ChartCard } from './ChartCard';
export type { ChartCardProps } from './ChartCard';

export { ChartGrid } from './ChartGrid';
export type { ChartGridProps } from './ChartGrid';

export {
  CHART_TYPES,
  CHART_TYPE_LABELS,
  isChartType,
} from './ChartTypes';
export type { ChartType, ChartData } from './ChartTypes';

export {
  applyChartTheme,
  getChartThemeColors,
  CHART_COLOR_PALETTE,
  CHART_SEQUENTIAL_PALETTE,
} from './chartTheme';
export type { ChartThemeColors, ApplyChartThemeOptions } from './chartTheme';

export {
  buildChart,
  buildBarChart,
  buildLineChart,
  buildScatterChart,
  buildPieChart,
  buildHistogram,
  buildBoxplot,
  buildHeatmap,
  computeBoxplotSummary,
} from './chartBuilders';
export type {
  ChartBuilderInput,
  CategoryValue,
  BoxplotSummary,
} from './chartBuilders';

export {
  downloadFile,
  toSafeFilename,
  exportChartToPng,
  exportOptionToSvg,
} from './chartExport';
