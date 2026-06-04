/**
 * Data preview table.
 *
 * Renders the first 10 rows of a parsed data file in an Ant Design `Table`
 * (Req 2.2). Columns are derived from `DataPreviewResponse.columns` and cell
 * values are coerced to a readable string, with missing/empty values shown as a
 * muted placeholder so data gaps are visible.
 */

import { Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { SPACING } from '../../../theme/tokens';
import type { DataPreviewResponse } from '../../../types/data';

const { Text } = Typography;

export interface DataPreviewTableProps {
  preview: DataPreviewResponse;
}

/** Coerce an arbitrary cell value into a display string. */
function renderCell(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return <Text type="secondary">—</Text>;
  }
  if (typeof value === 'object') {
    return <Text>{JSON.stringify(value)}</Text>;
  }
  return <Text>{String(value)}</Text>;
}

export function DataPreviewTable({ preview }: DataPreviewTableProps) {
  const columns: ColumnsType<Record<string, unknown>> = preview.columns.map((name) => ({
    title: name,
    dataIndex: name,
    key: name,
    ellipsis: true,
    render: (value: unknown) => renderCell(value),
  }));

  // Stable row keys: prefer an `id`-like column if present, else the index.
  const dataSource = preview.rows.map((row, index) => ({ ...row, __rowKey: index }));

  return (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: SPACING.sm }}>
        共 {preview.total_rows} 行 · {preview.total_columns} 列，下表展示前 {preview.rows.length} 行
        <Tag style={{ marginInlineStart: SPACING.sm }}>数据预览</Tag>
      </Text>
      <Table<Record<string, unknown>>
        size="small"
        columns={columns}
        dataSource={dataSource}
        rowKey="__rowKey"
        pagination={false}
        scroll={{ x: 'max-content' }}
        bordered
      />
    </div>
  );
}

export default DataPreviewTable;
