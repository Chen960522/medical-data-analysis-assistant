import { jsx as _jsx } from "react/jsx-runtime";
/**
 * ECharts wrapper component.
 *
 * A thin wrapper around `echarts-for-react`'s `ReactECharts` that:
 * - Applies the unified medical chart theme (Req 4 unified styling, 12.22-12.24).
 * - Enables interaction: zoom/filter via dataZoom + toolbox and hover tooltips
 *   (Req 4.7).
 * - Reads the active light/dark theme from the theme store so chart text and
 *   grid colors stay legible in both themes (Req 12.29).
 * - Resizes with its container (responsive, Req 12.6).
 * - Forwards a ref to the underlying ECharts instance so callers can export the
 *   chart (Req 4.8).
 */
import { forwardRef, useImperativeHandle, useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { useThemeStore } from '../../stores/themeStore';
import { applyChartTheme } from './chartTheme';
export const EChart = forwardRef(function EChart({ option, chartType, enableZoom = true, height = 320, style, ariaLabel }, ref) {
    const mode = useThemeStore((state) => state.mode);
    const chartRef = useRef(null);
    const themedOption = useMemo(() => applyChartTheme(option, { mode, chartType, enableZoom }), [option, mode, chartType, enableZoom]);
    useImperativeHandle(ref, () => ({
        getInstance: () => chartRef.current?.getEchartsInstance() ?? null,
    }), []);
    return (_jsx("div", { role: "img", "aria-label": ariaLabel, style: { width: '100%', height, ...style }, children: _jsx(ReactECharts, { ref: chartRef, option: themedOption, 
            // Replace the entire option on update so removed series/config don't
            // linger between different charts.
            notMerge: true, lazyUpdate: true, style: { width: '100%', height: '100%' }, 
            // Resize with the container so the chart stays responsive (Req 12.6).
            opts: { renderer: 'canvas' } }) }));
});
export default EChart;
