/**
 * Inline analysis results renderer.
 *
 * Renders the raw `analysis_results` payloads carried by an assistant message
 * compactly within the conversation (Req 9.10). The payload shapes are
 * arbitrary (the Agent may return `{ result_type, result_data }` objects or
 * free-form dicts), so values are rendered robustly:
 * - objects → a key/value `Descriptions`
 * - arrays of objects → a `Table`
 * - arrays of primitives → a `List`
 * - primitives → text
 *
 * Known `result_type` values are mapped to Chinese section titles, with a
 * fallback to the raw type (Req 3.1-3.5).
 */

import { Descriptions, List, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { SPACING } from '../../theme/tokens';

const { Text } = Typography;

/** Known result types mapped to Chinese section titles (Req 3.1-3.5). */
const RESULT_TYPE_LABELS: Record<string, string> = {
  descriptive: '描述性统计',
  correlation: '相关性分析',
  outlier: '异常值检测',
  trend: '趋势分析',
  group_comparison: '分组比较',
};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function primitiveToString(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, '');
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  return String(value);
}

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

/** Resolve the section title and body for a single result payload. */
function resolveResult(result: Record<string, unknown>): {
  title: string | null;
  body: unknown;
} {
  const resultType = typeof result.result_type === 'string' ? result.result_type : null;
  const title = resultType ? (RESULT_TYPE_LABELS[resultType] ?? resultType) : null;
  // Prefer a nested `result_data` payload when present; otherwise render the
  // whole object minus the type discriminator.
  if ('result_data' in result) {
    return { title, body: result.result_data };
  }
  if (resultType) {
    const { result_type: _omit, ...rest } = result;
    return { title, body: rest };
  }
  return { title: null, body: result };
}

export interface InlineAnalysisResultsProps {
  /** Raw analysis result payloads from the send response (Req 9.10). */
  results: Record<string, unknown>[];
}

export function InlineAnalysisResults({ results }: InlineAnalysisResultsProps) {
  if (results.length === 0) {
    return null;
  }

  return (
    <Space direction="vertical" size={SPACING.sm} style={{ width: '100%' }}>
      {results.map((result, index) => {
        const { title, body } = resolveResult(result);
        return (
          <div key={index}>
            {title ? (
              <Text strong style={{ display: 'block', marginBottom: SPACING.xs }}>
                {title}
              </Text>
            ) : null}
            {renderValue(body)}
          </div>
        );
      })}
    </Space>
  );
}

export default InlineAnalysisResults;
