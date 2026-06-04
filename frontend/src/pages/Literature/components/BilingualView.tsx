/**
 * Bilingual comparison view.
 *
 * Renders a side-by-side comparison of a literature record's original and
 * translated title/abstract (Req 10.29-10.34). The original text is on the LEFT
 * panel and the translation on the RIGHT, with paragraph-level alignment and
 * clear panel labels that name which side is the original/translation including
 * the data-source name (Req 10.33, 10.34).
 *
 * While the translation is in flight a loading state is shown; on failure an
 * error message is shown while still displaying the original text (Req 10.35).
 */

import { useMemo } from 'react';
import { Alert, Card, Col, Row, Space, Tag, Typography } from 'antd';

import { LoadingIndicator } from '../../../components/Common';
import { SPACING } from '../../../theme/tokens';
import type { BilingualContent } from '../../../types/literature';

const { Title, Paragraph, Text } = Typography;

export interface BilingualViewProps {
  /** Data-source label of the record being compared ("CNKI" / "PubMed"). */
  dataSource: string;
  /** The original title (always available from the record). */
  originalTitle: string;
  /** The original abstract (always available from the record). */
  originalAbstract?: string | null;
  /** The translation result, once loaded. */
  content?: BilingualContent | null;
  loading: boolean;
  /** Error message when the translation failed (Req 10.35). */
  error?: string | null;
}

/** Human label for a language code. */
const LANG_LABEL: Record<string, string> = { zh: '中文', en: '英文' };

/** Split text into paragraphs on blank lines / newlines for alignment. */
function toParagraphs(text?: string | null): string[] {
  if (!text) {
    return [];
  }
  const parts = text
    .split(/\n{1,}/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  return parts.length > 0 ? parts : [text.trim()];
}

export function BilingualView({
  dataSource,
  originalTitle,
  originalAbstract,
  content,
  loading,
  error,
}: BilingualViewProps) {
  const sourceLang = content?.source_language;
  const targetLang = content?.target_language;

  // Paragraph-level alignment: pair original and translated paragraphs by index.
  const rows = useMemo(() => {
    const originals = toParagraphs(originalAbstract ?? content?.original_abstract);
    const translations = toParagraphs(content?.translated_abstract);
    const length = Math.max(originals.length, translations.length);
    return Array.from({ length }, (_, index) => ({
      original: originals[index] ?? '',
      translated: translations[index] ?? '',
    }));
  }, [originalAbstract, content]);

  const originalLabel = sourceLang
    ? `原文（${LANG_LABEL[sourceLang] ?? sourceLang} · ${dataSource}）`
    : `原文（${dataSource}）`;
  const translatedLabel = targetLang
    ? `译文（${LANG_LABEL[targetLang] ?? targetLang}）`
    : '译文';

  return (
    <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
      {error ? (
        <Alert
          type="error"
          showIcon
          message="翻译暂时不可用"
          description={`${error} 下方仍展示原文内容。`}
        />
      ) : null}

      <Row gutter={[SPACING.md, SPACING.md]}>
        {/* LEFT: original (Req 10.33). */}
        <Col xs={24} md={12}>
          <Card
            size="small"
            variant="outlined"
            title={
              <Space size={SPACING.xs}>
                <Tag color="default">原文</Tag>
                <Text type="secondary">{originalLabel}</Text>
              </Space>
            }
            style={{ height: '100%' }}
          >
            <Title level={5} style={{ marginTop: 0 }}>
              {originalTitle}
            </Title>
            {rows.length > 0 ? (
              rows.map((row, index) => (
                <Paragraph key={`o-${index}`} style={{ marginBottom: SPACING.sm }}>
                  {row.original}
                </Paragraph>
              ))
            ) : (
              <Text type="secondary">无摘要内容</Text>
            )}
          </Card>
        </Col>

        {/* RIGHT: translation (Req 10.33). */}
        <Col xs={24} md={12}>
          <Card
            size="small"
            variant="outlined"
            title={
              <Space size={SPACING.xs}>
                <Tag color="blue">译文</Tag>
                <Text type="secondary">{translatedLabel}</Text>
              </Space>
            }
            style={{ height: '100%' }}
          >
            {loading ? (
              <LoadingIndicator tip="正在翻译…" size="default" />
            ) : content ? (
              <>
                <Title level={5} style={{ marginTop: 0 }}>
                  {content.translated_title ?? '—'}
                </Title>
                {rows.length > 0 ? (
                  rows.map((row, index) => (
                    <Paragraph key={`t-${index}`} style={{ marginBottom: SPACING.sm }}>
                      {row.translated || '—'}
                    </Paragraph>
                  ))
                ) : (
                  <Text type="secondary">无译文内容</Text>
                )}
              </>
            ) : (
              <Text type="secondary">翻译不可用</Text>
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

export default BilingualView;
