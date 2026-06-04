/**
 * Literature search result item.
 *
 * Renders a single `LiteratureRecord` with its title, authors, journal,
 * publication date, abstract preview (first 200 chars), and a data-source tag
 * ("CNKI" / "PubMed") — Req 10.22. The matched keywords are highlighted within
 * the title and abstract preview (Req 10.23). Clicking the title opens the
 * detail view (Req 10.26); a collection button saves the record (Req 10.36).
 */

import { Button, List, Space, Tag, Typography } from 'antd';
import { StarOutlined, TeamOutlined, CalendarOutlined, BookOutlined } from '@ant-design/icons';

import { SPACING } from '../../../theme/tokens';
import type { LiteratureRecord } from '../../../types/literature';
import { Highlight } from './Highlight';

const { Text, Paragraph, Link } = Typography;

export interface ResultItemProps {
  record: LiteratureRecord;
  /** The raw search keywords, used to highlight matches (Req 10.23). */
  keywords: string;
  /** Open the detail view for this record (Req 10.26). */
  onOpenDetail: (record: LiteratureRecord) => void;
  /** Save this record to a collection (Req 10.36). */
  onSave: (record: LiteratureRecord) => void;
}

/** Color the data-source tag distinctly per source (text label always shown). */
function sourceTagColor(source: string): string {
  return source === 'PubMed' ? 'geekblue' : 'volcano';
}

export function ResultItem({ record, keywords, onOpenDetail, onSave }: ResultItemProps) {
  const preview = record.abstract_preview ?? record.abstract ?? '';
  const authors = record.authors.length > 0 ? record.authors.join('、') : '未知作者';

  return (
    <List.Item
      actions={[
        <Button
          key="save"
          type="text"
          icon={<StarOutlined />}
          onClick={() => onSave(record)}
          aria-label={`收藏文献：${record.title}`}
        >
          收藏
        </Button>,
      ]}
    >
      <List.Item.Meta
        title={
          <Link onClick={() => onOpenDetail(record)} style={{ fontSize: 16 }}>
            <Highlight text={record.title} terms={keywords} />
          </Link>
        }
        description={
          <Space direction="vertical" size={SPACING.xs} style={{ width: '100%' }}>
            <Space size={SPACING.sm} wrap>
              <Tag color={sourceTagColor(record.data_source)}>{record.data_source}</Tag>
              <Text type="secondary">
                <TeamOutlined /> {authors}
              </Text>
              {record.journal ? (
                <Text type="secondary">
                  <BookOutlined /> {record.journal}
                </Text>
              ) : null}
              {record.publication_date ? (
                <Text type="secondary">
                  <CalendarOutlined /> {record.publication_date}
                </Text>
              ) : null}
              {record.citation_count != null ? (
                <Text type="secondary">被引 {record.citation_count}</Text>
              ) : null}
            </Space>
            {preview ? (
              <Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 3 }}>
                <Highlight text={preview} terms={keywords} />
              </Paragraph>
            ) : null}
          </Space>
        }
      />
    </List.Item>
  );
}

export default ResultItem;
