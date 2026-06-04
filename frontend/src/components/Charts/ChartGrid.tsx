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
import type { ChartData } from './ChartTypes';

export interface ChartGridProps {
  /** The charts to display. */
  charts: ChartData[];
  /** Per-chart body height. Defaults to 320px. */
  chartHeight?: number;
  /** Message shown when there are no charts. */
  emptyText?: string;
}

export function ChartGrid({
  charts,
  chartHeight = 320,
  emptyText = '暂无图表，完成数据分析后将在此展示可视化结果。',
}: ChartGridProps) {
  const { isDesktop } = useResponsive();

  if (charts.length === 0) {
    return <Empty description={emptyText} />;
  }

  // Two columns on desktop, one column on tablet (Req 12.25, 12.5).
  const span = isDesktop ? 12 : 24;

  return (
    <Row gutter={[SPACING.md, SPACING.md]}>
      {charts.map((chart) => (
        <Col key={chart.id} span={span}>
          <ChartCard chart={chart} height={chartHeight} />
        </Col>
      ))}
    </Row>
  );
}

export default ChartGrid;
