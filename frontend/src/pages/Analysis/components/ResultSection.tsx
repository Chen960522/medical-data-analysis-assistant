/**
 * Analysis result section.
 *
 * Renders a single {@link AnalysisResult} as a titled card. The `result_type`
 * is mapped to a Chinese section title (descriptive statistics, correlation,
 * outliers, trend, group comparison) with a fallback to the raw type
 * (Req 3.1-3.5). The arbitrary `result_data` payload is rendered robustly:
 * - objects → a key/value `Descriptions`
 * - arrays of objects → a `Table`
 * - arrays of primitives → a `List`
 * - primitives → text
 *
 * Nested values are rendered recursively so deep result shapes stay readable.
 */

import { Card, Descriptions, List, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { SPACING } from '../../../theme/tokens';
import type { AnalysisResult } from '../../../types/analysis';

const { Text, Paragraph } = Typography;

/** Known result types mapped to Chinese section titles (Req 3.1-3.5). */
export const RESULT_TYPE_LABELS: Record<string, string> = {
  descriptive: '描述性统计',
  correlation: '相关性分析',
  outlier: '异常值检测',
  trend: '趋势分析',
  group_comparison: '分组比较',
};

/** Resolve a result type to its Chinese section title, falling back to the raw type. */
export function resultTypeLabel(resultType: string): string {
  return RESULT_TYPE_LABELS[resultType] ?? resultType;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function primitiveToString(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'number') {
    // Trim long floats for readability.
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, '');
  }
  return String(value);
}

/** Recursively render an arbitrary value into a React node. */
function renderValue(value: unknown): React.ReactNode {
  if (Array.isArray(value)) {
    return renderArray(value);
  }
  if (isPlainObject(value)) {
    return renderObject(value);
  }
  return <Text>{primitiveToString(value)}</Text>;
}

function renderArray(items: unknown[]): React.ReactNode {
  if (items.length === 0) {
    return <Text type="secondary">—</Text>;
  }

  // Array of homogeneous objects → table with a union of keys as columns.
  if (items.every((item) => isPlainObject(item))) {
    const records = items as Record<string, unknown>[];
    const keys = Array.from(
      records.reduce<Set<string>>((set, record) => {
        Object.keys(record).forEach((key) => set.add(key));
        return set;
      }, new Set<string>()),
    );
    const columns: ColumnsType<Record<string, unknown>> = keys.map((key) => ({
      title: key,
      dataIndex: key,
      key,
      render: (cell: unknown) => renderValue(cell),
    }));
    const dataSource = records.map((record, index) => ({ ...record, __rowKey: index }));
    return (
      <Table<Record<string, unknown>>
        size="small"
        columns={columns}
        dataSource={dataSource}
        rowKey="__rowKey"
        pagination={false}
        scroll={{ x: 'max-content' }}
        bordered
      />
    );
  }

  // Array of primitives (or mixed) → list.
  return (
    <List
      size="small"
      dataSource={items}
      renderItem={(item) => <List.Item>{renderValue(item)}</List.Item>}
    />
  );
}

function renderObject(obj: Record<string, unknown>): React.ReactNode {
  const entries = Object.entries(obj);
  if (entries.length === 0) {
    return <Text type="secondary">—</Text>;
  }
  return (
    <Descriptions column={1} size="small" bordered>
      {entries.map(([key, value]) => (
        <Descriptions.Item key={key} label={key}>
          {renderValue(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

export interface ResultSectionProps {
  result: AnalysisResult;
}

export function ResultSection({ result }: ResultSectionProps) {
  const title = resultTypeLabel(result.result_type);
  const data = result.result_data;
  const hasData = data && Object.keys(data).length > 0;

  return (
    <Card
      title={title}
      variant="outlined"
      style={{ marginBottom: SPACING.md }}
      styles={{ body: { paddingBlock: SPACING.md } }}
    >
      {hasData ? (
        renderValue(data)
      ) : (
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          暂无该维度的详细数据。
        </Paragraph>
      )}
    </Card>
  );
}

export default ResultSection;
