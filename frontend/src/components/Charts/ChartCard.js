import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
/**
 * Chart card.
 *
 * Wraps a single chart in an Ant Design `Card` with the chart title and a
 * toolbar offering:
 * - Export to PNG (Req 4.8) via the live ECharts instance.
 * - Export to SVG (Req 4.8) via an off-screen SVG-renderer instance.
 * - Fullscreen view (Req 9.12, 12.22-12.25) opening the chart in a `Modal` at
 *   full size.
 *
 * The chart itself renders through {@link EChart}, which applies the unified
 * medical theme and interaction affordances (zoom/filter/hover, Req 4.7).
 */
import { useMemo, useRef, useState } from 'react';
import { Card, Dropdown, Modal, Space, Tooltip, Button } from 'antd';
import { DownloadOutlined, FullscreenOutlined, } from '@ant-design/icons';
import { useThemeStore } from '../../stores/themeStore';
import { useNotify } from '../../hooks/useNotify';
import { PALETTE, SPACING } from '../../theme/tokens';
import { EChart } from './EChart';
import { applyChartTheme } from './chartTheme';
import { exportChartToPng, exportOptionToSvg } from './chartExport';
import { CHART_TYPE_LABELS, isChartType } from './ChartTypes';
export function ChartCard({ chart, height = 320 }) {
    const mode = useThemeStore((state) => state.mode);
    const notify = useNotify();
    const chartHandleRef = useRef(null);
    const fullscreenHandleRef = useRef(null);
    const [fullscreen, setFullscreen] = useState(false);
    const chartType = chart.chart_type;
    const typeLabel = isChartType(chartType) ? CHART_TYPE_LABELS[chartType] : '图表';
    // Describe the chart for screen readers; never rely on color alone (Req 12.34).
    const ariaLabel = `${chart.title}（${typeLabel}）`;
    // Background used for PNG export differs by theme so exported images stay
    // legible (Req 12.29).
    const exportBackground = mode === 'dark' ? PALETTE.neutral.gray8 : PALETTE.neutral.white;
    const handleExportPng = () => {
        const instance = chartHandleRef.current?.getInstance();
        if (!instance) {
            notify.error('图表导出失败', '图表尚未加载完成，请稍后重试。');
            return;
        }
        exportChartToPng(instance, chart.title || 'chart', exportBackground);
        notify.success('已导出 PNG 图片');
    };
    // The SVG export re-applies the unified theme so the downloaded file matches
    // the on-screen chart (Req 4.8).
    const themedOption = useMemo(() => applyChartTheme(chart.echarts_option, { mode, chartType }), [chart.echarts_option, mode, chartType]);
    const handleExportSvg = () => {
        try {
            exportOptionToSvg(themedOption, chart.title || 'chart');
            notify.success('已导出 SVG 图片');
        }
        catch {
            notify.error('图表导出失败', '生成 SVG 时出错，请稍后重试。');
        }
    };
    const exportMenu = {
        items: [
            { key: 'png', label: '下载为 PNG' },
            { key: 'svg', label: '下载为 SVG' },
        ],
        onClick: ({ key }) => {
            if (key === 'png') {
                handleExportPng();
            }
            else if (key === 'svg') {
                handleExportSvg();
            }
        },
    };
    const toolbar = (_jsxs(Space, { size: SPACING.xs, children: [_jsx(Dropdown, { menu: exportMenu, trigger: ['click'], children: _jsx(Tooltip, { title: "\u5BFC\u51FA\u56FE\u8868", children: _jsx(Button, { type: "text", size: "small", icon: _jsx(DownloadOutlined, {}), "aria-label": `导出图表：${chart.title}` }) }) }), _jsx(Tooltip, { title: "\u5168\u5C4F\u67E5\u770B", children: _jsx(Button, { type: "text", size: "small", icon: _jsx(FullscreenOutlined, {}), "aria-label": `全屏查看图表：${chart.title}`, onClick: () => setFullscreen(true) }) })] }));
    return (_jsxs(_Fragment, { children: [_jsx(Card, { title: chart.title, extra: toolbar, styles: { body: { padding: SPACING.sm } }, children: _jsx(EChart, { ref: chartHandleRef, option: chart.echarts_option, chartType: chartType, height: height, ariaLabel: ariaLabel }) }), _jsx(Modal, { title: chart.title, open: fullscreen, onCancel: () => setFullscreen(false), footer: null, width: "90vw", style: { top: SPACING.lg }, destroyOnClose: true, children: _jsx(EChart, { ref: fullscreenHandleRef, option: chart.echarts_option, chartType: chartType, height: "72vh", ariaLabel: ariaLabel }) })] }));
}
export default ChartCard;
