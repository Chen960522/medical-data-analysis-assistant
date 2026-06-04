/**
 * Literature search result list.
 *
 * Renders the merged, paginated result list (Req 10.22) with a results summary
 * showing the merged total and per-source counts (Req 10.28), sorting controls
 * (relevance / date / citations, Req 10.24), and a client-side source filter to
 * view CNKI-only / PubMed-only / both within the fetched page (Req 10.25).
 * Pagination re-fetches with the new page (default 20/page, Req 10.5).
 */

import { useMemo } from 'react';
import { Empty, List, Pagination, Segmented, Select, Space, Tag, Typography } from 'antd';

import { LoadingIndicator } from '../../../components/Common';
import { SOURCE_LABELS } from '../../../types/literature';
import type { LiteratureRecord, SortBy } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';
import { ResultItem } from './ResultItem';

const { Text } = Typography;

/** View-level source filter applied to the already-fetched page (Req 10.25). */
export type SourceFilter = 'all' | 'CNKI' | 'PubMed';

export interface ResultListProps {
  records: LiteratureRecord[];
  keywords: string;
  loading: boolean;
  /** Whether a search has been executed at least once. */
  searched: boolean;
  page: number;
  pageSize: number;
  total: number;
  totals: Record<string, number>;
  sortBy: SortBy;
  sourceFilter: SourceFilter;
  onSortChange: (sortBy: SortBy) => void;
  onSourceFilterChange: (filter: SourceFilter) => void;
  onPageChange: (page: number) => void;
  onOpenDetail: (record: LiteratureRecord) => void;
  onSave: (record: LiteratureRecord) => void;
}

const SORT_OPTIONS: { label: string; value: SortBy }[] = [
  { label: '相关性', value: 'relevance' },
  { label: '最新发表', value: 'date' },
  { label: '引用数', value: 'citations' },
];

export function ResultList({
  records,
  keywords,
  loading,
  searched,
  page,
  pageSize,
  total,
  totals,
  sortBy,
  sourceFilter,
  onSortChange,
  onSourceFilterChange,
  onPageChange,
  onOpenDetail,
  onSave,
}: ResultListProps) {
  // Client-side source filter on the merged page (Req 10.25).
  const visibleRecords = useMemo(() => {
    if (sourceFilter === 'all') {
      return records;
    }
    return records.filter((record) => record.data_source === sourceFilter);
  }, [records, sourceFilter]);

  if (loading) {
    return <LoadingIndicator tip="正在检索文献…" />;
  }

  if (!searched) {
    return <Empty description="请输入关键词并开始搜索" />;
  }

  if (total === 0) {
    return (
      <Empty description="未找到匹配的文献，请尝试更换或精简关键词、调整数据源或时间范围" />
    );
  }

  const cnkiTotal = totals[SOURCE_LABELS.cnki] ?? 0;
  const pubmedTotal = totals[SOURCE_LABELS.pubmed] ?? 0;

  return (
    <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
      {/* Results summary with per-source totals (Req 10.28). */}
      <Space size={SPACING.sm} wrap>
        <Text strong>共 {total} 条结果</Text>
        <Tag color="volcano">CNKI {cnkiTotal}</Tag>
        <Tag color="geekblue">PubMed {pubmedTotal}</Tag>
      </Space>

      {/* Sorting (Req 10.24) + client-side source filter (Req 10.25). */}
      <Space size={SPACING.md} wrap>
        <Space size={SPACING.xs}>
          <Text type="secondary">排序：</Text>
          <Select<SortBy>
            value={sortBy}
            onChange={onSortChange}
            options={SORT_OPTIONS}
            style={{ width: 140 }}
          />
        </Space>
        <Space size={SPACING.xs}>
          <Text type="secondary">数据源：</Text>
          <Segmented<SourceFilter>
            value={sourceFilter}
            onChange={(value) => onSourceFilterChange(value as SourceFilter)}
            options={[
              { label: '全部', value: 'all' },
              { label: 'CNKI', value: 'CNKI' },
              { label: 'PubMed', value: 'PubMed' },
            ]}
          />
        </Space>
      </Space>

      {visibleRecords.length === 0 ? (
        <Empty description="当前数据源筛选下没有结果" />
      ) : (
        <List
          itemLayout="vertical"
          dataSource={visibleRecords}
          rowKey={(record) =>
            `${record.data_source}:${record.external_id ?? record.doi ?? record.title}`
          }
          renderItem={(record) => (
            <ResultItem
              record={record}
              keywords={keywords}
              onOpenDetail={onOpenDetail}
              onSave={onSave}
            />
          )}
        />
      )}

      {/* Server-side pagination re-fetches the page (Req 10.5). */}
      <div style={{ textAlign: 'right' }}>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger={false}
          onChange={onPageChange}
        />
      </div>
    </Space>
  );
}

export default ResultList;
