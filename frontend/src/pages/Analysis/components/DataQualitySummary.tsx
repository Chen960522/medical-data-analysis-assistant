/**
 * Data quality summary.
 *
 * Displays a data quality report (Req 2.6): overall totals (rows, columns,
 * missing-value percentage) via `Statistic`s, and a per-column table listing
 * each column's detected dtype and missing count/percentage. Columns with
 * missing values are flagged with a warning tag so data gaps are easy to spot.
 */

import { Card, Col, Row, Statistic, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PALETTE, SPACING } from '../../../theme/tokens';
import type { ColumnQuality, DataQualityResponse } from '../../../types/data';

export interface DataQualitySummaryProps {
  quality: DataQualityResponse;
}

/** Map a backend dtype string to a Chinese label. */
const DTYPE_LABELS: Record<string, string> = {
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

function dtypeLabel(dtype: string): string {
  return DTYPE_LABELS[dtype.toLowerCase()] ?? dtype;
}

export function DataQualitySummary({ quality }: DataQualitySummaryProps) {
  const columns: ColumnsType<ColumnQuality> = [
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
      render: (dtype: string) => <Tag>{dtypeLabel(dtype)}</Tag>,
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
      render: (pct: number) =>
        pct > 0 ? (
          <Tag color="warning">{pct.toFixed(1)}%</Tag>
        ) : (
          <Tag color="success">0%</Tag>
        ),
    },
  ];

  const missingPct = quality.missing_value_percentage;

  return (
    <div>
      <Row gutter={[SPACING.md, SPACING.md]} style={{ marginBottom: SPACING.md }}>
        <Col xs={24} sm={8}>
          <Card variant="outlined">
            <Statistic title="总行数" value={quality.total_rows} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card variant="outlined">
            <Statistic title="总列数" value={quality.total_columns} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card variant="outlined">
            <Statistic
              title="整体缺失值占比"
              value={missingPct}
              precision={1}
              suffix="%"
              valueStyle={{ color: missingPct > 0 ? PALETTE.warning : PALETTE.success }}
            />
          </Card>
        </Col>
      </Row>
      <Table<ColumnQuality>
        size="small"
        columns={columns}
        dataSource={quality.columns}
        rowKey="name"
        pagination={false}
        bordered
        scroll={{ x: 'max-content' }}
      />
    </div>
  );
}

export default DataQualitySummary;
