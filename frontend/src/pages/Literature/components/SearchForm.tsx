/**
 * Literature search form.
 *
 * Provides the keyword search input (Chinese + English, Req 10.2), an advanced
 * filter section (author, journal, publication date range, subject, Req 10.3),
 * and a data-source selector (CNKI / PubMed, defaulting to both, Req 10.6-10.7).
 *
 * As the user types keywords, it requests MeSH term suggestions (debounced) and
 * surfaces them as clickable tags that append to the query (Req 10.20). On
 * submit it emits the assembled search criteria to the parent page.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Checkbox,
  Collapse,
  DatePicker,
  Form,
  Input,
  Space,
  Tag,
  Typography,
} from 'antd';
import { SearchOutlined, BulbOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';

import { literatureService } from '../../../services/literatureService';
import { DATA_SOURCE_IDS, SOURCE_LABELS } from '../../../types/literature';
import type { DataSourceId } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';

const { Text } = Typography;
const { RangePicker } = DatePicker;

/** Criteria assembled by the form and emitted on submit. */
export interface SearchCriteria {
  keywords: string;
  author?: string;
  journal?: string;
  subject?: string;
  date_from?: string;
  date_to?: string;
  sources: DataSourceId[];
}

interface SearchFormFields {
  keywords: string;
  author?: string;
  journal?: string;
  subject?: string;
  dateRange?: [Dayjs | null, Dayjs | null] | null;
  sources: DataSourceId[];
}

export interface SearchFormProps {
  /** Invoked with the assembled criteria when the user submits a search. */
  onSearch: (criteria: SearchCriteria) => void;
  /** Whether a search is currently in flight (drives the submit button). */
  loading?: boolean;
}

/** Debounce delay for MeSH term suggestions (Req 10.20). */
const MESH_DEBOUNCE_MS = 350;

const SOURCE_OPTIONS = DATA_SOURCE_IDS.map((id) => ({
  label: SOURCE_LABELS[id],
  value: id,
}));

export function SearchForm({ onSearch, loading = false }: SearchFormProps) {
  const [form] = Form.useForm<SearchFormFields>();
  const [keywords, setKeywords] = useState('');
  const [meshTerms, setMeshTerms] = useState<string[]>([]);

  const debounceRef = useRef<number | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch MeSH suggestions (debounced) whenever the keyword input changes.
  useEffect(() => {
    const query = keywords.trim();
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current);
    }
    if (query.length < 2) {
      setMeshTerms([]);
      return;
    }
    debounceRef.current = window.setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      void (async () => {
        try {
          const response = await literatureService.suggestMesh(query, controller.signal);
          setMeshTerms(response.terms.slice(0, 8));
        } catch {
          // Suggestions are best-effort; ignore failures (incl. aborts).
        }
      })();
    }, MESH_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current);
      }
    };
  }, [keywords]);

  // Clean up any in-flight suggestion request on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  /** Append a suggested MeSH term to the keyword input (Req 10.20). */
  const appendMeshTerm = useCallback(
    (term: string) => {
      const current = form.getFieldValue('keywords') as string | undefined;
      const existing = (current ?? '').trim();
      if (existing.toLowerCase().includes(term.toLowerCase())) {
        return;
      }
      const next = existing ? `${existing} ${term}` : term;
      form.setFieldsValue({ keywords: next });
      setKeywords(next);
    },
    [form],
  );

  const handleFinish = useCallback(
    (values: SearchFormFields) => {
      const [start, end] = values.dateRange ?? [];
      const criteria: SearchCriteria = {
        keywords: values.keywords.trim(),
        author: values.author?.trim() || undefined,
        journal: values.journal?.trim() || undefined,
        subject: values.subject?.trim() || undefined,
        date_from: start ? start.format('YYYY-MM-DD') : undefined,
        date_to: end ? end.format('YYYY-MM-DD') : undefined,
        sources: values.sources?.length ? values.sources : [...DATA_SOURCE_IDS],
      };
      onSearch(criteria);
    },
    [onSearch],
  );

  const advancedItems = useMemo(
    () => [
      {
        key: 'advanced',
        label: '高级搜索筛选',
        children: (
          <Space direction="vertical" size={SPACING.sm} style={{ width: '100%' }}>
            <Form.Item name="author" label="作者" style={{ marginBottom: SPACING.sm }}>
              <Input allowClear placeholder="按作者姓名筛选" />
            </Form.Item>
            <Form.Item name="journal" label="期刊" style={{ marginBottom: SPACING.sm }}>
              <Input allowClear placeholder="按期刊名称筛选" />
            </Form.Item>
            <Form.Item name="subject" label="学科领域" style={{ marginBottom: SPACING.sm }}>
              <Input allowClear placeholder="按学科领域筛选" />
            </Form.Item>
            <Form.Item name="dateRange" label="发表时间" style={{ marginBottom: 0 }}>
              <RangePicker style={{ width: '100%' }} allowEmpty={[true, true]} />
            </Form.Item>
          </Space>
        ),
      },
    ],
    [],
  );

  return (
    <Form<SearchFormFields>
      form={form}
      layout="vertical"
      initialValues={{ keywords: '', sources: [...DATA_SOURCE_IDS] }}
      onFinish={handleFinish}
    >
      <Form.Item
        name="keywords"
        label="关键词"
        rules={[{ required: true, message: '请输入检索关键词' }]}
        style={{ marginBottom: SPACING.sm }}
      >
        <Input
          allowClear
          size="large"
          prefix={<SearchOutlined />}
          placeholder="输入中文或英文检索关键词"
          onChange={(event) => setKeywords(event.target.value)}
          onPressEnter={() => form.submit()}
        />
      </Form.Item>

      {/* MeSH term suggestions (Req 10.20). */}
      {meshTerms.length > 0 ? (
        <div style={{ marginBottom: SPACING.md }}>
          <Space size={SPACING.xs} align="center" wrap>
            <Text type="secondary">
              <BulbOutlined /> MeSH 术语建议：
            </Text>
            {meshTerms.map((term) => (
              <Tag
                key={term}
                color="blue"
                style={{ cursor: 'pointer' }}
                onClick={() => appendMeshTerm(term)}
              >
                {term}
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}

      {/* Data-source selector (Req 10.6-10.7). */}
      <Form.Item
        name="sources"
        label="数据源"
        rules={[{ required: true, message: '请至少选择一个数据源' }]}
        style={{ marginBottom: SPACING.md }}
      >
        <Checkbox.Group options={SOURCE_OPTIONS} />
      </Form.Item>

      <Collapse ghost items={advancedItems} style={{ marginBottom: SPACING.md }} />

      <Form.Item style={{ marginBottom: 0 }}>
        <Button
          type="primary"
          htmlType="submit"
          icon={<SearchOutlined />}
          loading={loading}
          block
        >
          搜索文献
        </Button>
      </Form.Item>
    </Form>
  );
}

export default SearchForm;
