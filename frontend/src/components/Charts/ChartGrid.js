import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Chart grid.
 *
 * Arranges multiple {@link ChartCard}s in a balanced, responsive grid for the
 * analysis dashboard (Req 12.25): two columns on desktop and a single column on
 * tablet (Req 12.5, 12.6), with consistent sizing and spacing on the 8px grid
 * (Req 12.11). Renders an empty state when there are no charts.
 */
import { Empty, Row, Col } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { SPACING } from '../../theme/tokens';
import { ChartCard } from './ChartCard';
export function ChartGrid({ charts, chartHeight = 320, emptyText = '暂无图表，完成数据分析后将在此展示可视化结果。', }) {
    const { isDesktop } = useResponsive();
    if (charts.length === 0) {
        return _jsx(Empty, { description: emptyText });
    }
    // Two columns on desktop, one column on tablet (Req 12.25, 12.5).
    const span = isDesktop ? 12 : 24;
    return (_jsx(Row, { gutter: [SPACING.md, SPACING.md], children: charts.map((chart) => (_jsx(Col, { span: span, children: _jsx(ChartCard, { chart: chart, height: chartHeight }) }, chart.id))) }));
}
export default ChartGrid;
