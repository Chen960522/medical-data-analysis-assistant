/**
 * Literature detail view.
 *
 * A drawer showing the full detail of a `LiteratureRecord`: complete abstract,
 * all authors, keywords, journal/source info, and the data-source label
 * (Req 10.26). It provides a 收藏 (save) button (Req 10.36) and a 双语对比
 * (bilingual) toggle that, when activated, translates the title + abstract and
 * renders the side-by-side comparison (Req 10.29-10.35).
 *
 * Because search results are ephemeral, the detail uses the record already in
 * the list (it carries the full abstract). When the record has an external id,
 * it also fetches the full detail via the backend to fill in any missing
 * fields (best-effort).
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Descriptions,
  Divider,
  Drawer,
  Segmented,
  Space,
  Tag,
  Typography,
} from 'antd';
import { ExperimentOutlined, StarOutlined, TranslationOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { useNotify } from '../../../hooks/useNotify';
import { literatureService } from '../../../services/literatureService';
import { useLiteratureReferenceStore } from '../../../stores/literatureReferenceStore';
import { SOURCE_LABELS } from '../../../types/literature';
import type { BilingualContent, DataSourceId, LiteratureRecord } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';
import { BilingualView } from './BilingualView';

const { Title, Paragraph, Text } = Typography;

/** View mode within the detail drawer. */
type DetailMode = 'detail' | 'bilingual';

export interface LiteratureDetailProps {
  open: boolean;
  record: LiteratureRecord | null;
  onClose: () => void;
  /** Save the current record to a collection (Req 10.36). */
  onSave: (record: LiteratureRecord) => void;
}

/** Map a canonical data-source label back to its lowercase identifier. */
function toSourceId(dataSource: string): DataSourceId {
  return dataSource === SOURCE_LABELS.pubmed ? 'pubmed' : 'cnki';
}

export function LiteratureDetail({ open, record, onClose, onSave }: LiteratureDetailProps) {
  const notify = useNotify();
  const navigate = useNavigate();
  const setReference = useLiteratureReferenceStore((state) => state.setReference);
  const [mode, setMode] = useState<DetailMode>('detail');
  const [detail, setDetail] = useState<LiteratureRecord | null>(record);

  const [bilingual, setBilingual] = useState<BilingualContent | null>(null);
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);

  // Reset transient state whenever a new record is opened.
  useEffect(() => {
    setDetail(record);
    setMode('detail');
    setBilingual(null);
    setTranslateError(null);
  }, [record]);

  // Best-effort full-detail fetch when an external id is available (Req 10.26).
  useEffect(() => {
    if (!open || !record || !record.external_id) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const full = await literatureService.getDetail(
          record.external_id as string,
          toSourceId(record.data_source),
          controller.signal,
        );
        setDetail(full);
      } catch {
        // Fall back to the list record; ignore detail fetch failures.
      }
    })();
    return () => controller.abort();
  }, [open, record]);

  /** Activate the bilingual view, translating the record on first open (Req 10.29-10.35). */
  const handleToggleBilingual = useCallback(async () => {
    if (!detail) {
      return;
    }
    setMode('bilingual');
    if (bilingual || translating) {
      return;
    }
    setTranslating(true);
    setTranslateError(null);
    try {
      const result = await literatureService.translate(
        detail.external_id ?? detail.title,
        {
          title: detail.title,
          abstract: detail.abstract ?? undefined,
          source: toSourceId(detail.data_source),
        },
      );
      setBilingual(result);
    } catch (err) {
      setTranslateError(err instanceof Error ? err.message : '请稍后重试。');
    } finally {
      setTranslating(false);
    }
  }, [detail, bilingual, translating]);

  const current = detail ?? record;

  /**
   * Reference this literature's methodology in the analysis chat (Req 10.44, 10.45).
   *
   * Stages the record's title, abstract, and data source, then navigates to the
   * analysis page where the Chat panel seeds the composer with the literature
   * context so the User can ask the AI to apply a similar analytical approach.
   */
  const handleReferenceMethodology = useCallback(() => {
    if (!current) {
      return;
    }
    setReference({
      title: current.title,
      abstract: current.abstract ?? null,
      data_source: current.data_source,
    });
    onClose();
    notify.info('已将该文献方法学引入分析对话');
    navigate('/analysis');
  }, [current, setReference, onClose, notify, navigate]);

  return (
    <Drawer
      title="文献详情"
      open={open}
      onClose={onClose}
      width={760}
      extra={
        current ? (
          <Space>
            <Button
              icon={<TranslationOutlined />}
              type={mode === 'bilingual' ? 'primary' : 'default'}
              onClick={() => void handleToggleBilingual()}
            >
              双语对比
            </Button>
            <Button icon={<ExperimentOutlined />} onClick={handleReferenceMethodology}>
              引用方法学
            </Button>
            <Button
              icon={<StarOutlined />}
              onClick={() => {
                onSave(current);
                notify.info('请选择收藏夹以保存该文献');
              }}
            >
              收藏
            </Button>
          </Space>
        ) : null
      }
    >
      {current ? (
        <>
          <Segmented<DetailMode>
            value={mode}
            onChange={(value) => {
              const next = value as DetailMode;
              if (next === 'bilingual') {
                void handleToggleBilingual();
              } else {
                setMode('detail');
              }
            }}
            options={[
              { label: '详情', value: 'detail' },
              { label: '双语对比', value: 'bilingual' },
            ]}
            style={{ marginBottom: SPACING.md }}
          />

          {mode === 'detail' ? (
            <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
              <Title level={4} style={{ marginBottom: 0 }}>
                {current.title}
              </Title>

              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="数据源">
                  <Tag color={current.data_source === SOURCE_LABELS.pubmed ? 'geekblue' : 'volcano'}>
                    {current.data_source}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="作者">
                  {current.authors.length > 0 ? current.authors.join('、') : '未知作者'}
                </Descriptions.Item>
                {current.journal ? (
                  <Descriptions.Item label="期刊">{current.journal}</Descriptions.Item>
                ) : null}
                {current.publication_date ? (
                  <Descriptions.Item label="发表时间">
                    {current.publication_date}
                  </Descriptions.Item>
                ) : null}
                {current.doi ? <Descriptions.Item label="DOI">{current.doi}</Descriptions.Item> : null}
                {current.external_id ? (
                  <Descriptions.Item label="标识">{current.external_id}</Descriptions.Item>
                ) : null}
                {current.citation_count != null ? (
                  <Descriptions.Item label="被引次数">{current.citation_count}</Descriptions.Item>
                ) : null}
              </Descriptions>

              {current.keywords.length > 0 ? (
                <div>
                  <Text strong>关键词：</Text>
                  <Space size={SPACING.xs} wrap style={{ marginTop: SPACING.xs }}>
                    {current.keywords.map((keyword) => (
                      <Tag key={keyword}>{keyword}</Tag>
                    ))}
                  </Space>
                </div>
              ) : null}

              <Divider style={{ margin: `${SPACING.sm}px 0` }} />

              <div>
                <Text strong>摘要</Text>
                <Paragraph style={{ marginTop: SPACING.xs }}>
                  {current.abstract ?? '暂无摘要'}
                </Paragraph>
              </div>
            </Space>
          ) : (
            <BilingualView
              dataSource={current.data_source}
              originalTitle={current.title}
              originalAbstract={current.abstract}
              content={bilingual}
              loading={translating}
              error={translateError}
            />
          )}
        </>
      ) : null}
    </Drawer>
  );
}

export default LiteratureDetail;
