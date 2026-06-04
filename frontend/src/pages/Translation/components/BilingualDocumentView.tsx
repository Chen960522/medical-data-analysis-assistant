/**
 * Bilingual document comparison view for translated PDFs (Req 11.30-11.36).
 *
 * Renders the index-aligned `original_paragraphs` / `translated_paragraphs`
 * arrays side by side — original on the LEFT, translation on the RIGHT — with
 * paragraph-level alignment (row `i` pairs index `i` of each array, Req 11.31).
 * Panels carry clear labels naming which side is the original/translation
 * including the detected source language (Req 11.33).
 *
 * Features:
 * - View switch (双语并排 / 仅原文 / 仅翻译) via a Segmented control (Req 11.35);
 *   single-language modes render one panel full width.
 * - Synchronized scrolling between the two panels (Req 11.34), guarded against
 *   feedback loops with a ref flag.
 * - Click a paragraph to highlight the corresponding paragraph in the other
 *   panel (Req 11.36): clicking row `i` highlights index `i` on both sides.
 */

import { useMemo, useRef, useState } from 'react';
import { Card, Empty, Segmented, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import { GEOMETRY, PALETTE, SPACING } from '../../../theme/tokens';
import { languageLabel } from '../../../types/translation';
import type { DocumentViewMode, LanguageCode } from '../../../types/translation';

const { Text } = Typography;

export interface BilingualDocumentViewProps {
  originalParagraphs: string[];
  translatedParagraphs: string[];
  sourceLanguage?: LanguageCode | null;
  targetLanguage?: LanguageCode | null;
}

interface ParagraphRow {
  original: string;
  translated: string;
}

/** Fixed panel height so synchronized scrolling has a scrollable viewport. */
const PANEL_HEIGHT = 560;

const paragraphBaseStyle: CSSProperties = {
  padding: SPACING.sm,
  borderRadius: GEOMETRY.borderRadius,
  marginBottom: SPACING.sm,
  cursor: 'pointer',
  transition: 'background-color 150ms ease',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

const selectedStyle: CSSProperties = {
  backgroundColor: 'rgba(22, 119, 255, 0.12)',
  outline: `1px solid ${PALETTE.primary}`,
};

export function BilingualDocumentView({
  originalParagraphs,
  translatedParagraphs,
  sourceLanguage,
  targetLanguage,
}: BilingualDocumentViewProps) {
  const [viewMode, setViewMode] = useState<DocumentViewMode>('bilingual');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const originalRef = useRef<HTMLDivElement | null>(null);
  const translatedRef = useRef<HTMLDivElement | null>(null);
  // Guards against scroll feedback loops while syncing the two panels.
  const isSyncingRef = useRef(false);

  // Pair original and translated paragraphs by index (Req 11.31).
  const rows = useMemo<ParagraphRow[]>(() => {
    const length = Math.max(originalParagraphs.length, translatedParagraphs.length);
    return Array.from({ length }, (_, index) => ({
      original: originalParagraphs[index] ?? '',
      translated: translatedParagraphs[index] ?? '',
    }));
  }, [originalParagraphs, translatedParagraphs]);

  /** Synchronize scroll position proportionally between panels (Req 11.34). */
  const handleScroll = (source: 'original' | 'translated') => () => {
    if (viewMode !== 'bilingual') {
      return;
    }
    if (isSyncingRef.current) {
      isSyncingRef.current = false;
      return;
    }
    const fromEl = source === 'original' ? originalRef.current : translatedRef.current;
    const toEl = source === 'original' ? translatedRef.current : originalRef.current;
    if (!fromEl || !toEl) {
      return;
    }
    const fromScrollable = fromEl.scrollHeight - fromEl.clientHeight;
    const toScrollable = toEl.scrollHeight - toEl.clientHeight;
    if (fromScrollable <= 0 || toScrollable <= 0) {
      return;
    }
    const ratio = fromEl.scrollTop / fromScrollable;
    isSyncingRef.current = true;
    toEl.scrollTop = ratio * toScrollable;
  };

  /** Toggle highlight of the corresponding paragraph pair (Req 11.36). */
  const handleParagraphClick = (index: number) => {
    setSelectedIndex((current) => (current === index ? null : index));
  };

  const sourceLabel = `原文（${languageLabel(sourceLanguage)}）`;
  const targetLabel = `译文（${languageLabel(targetLanguage)}）`;

  const showOriginal = viewMode === 'bilingual' || viewMode === 'original';
  const showTranslated = viewMode === 'bilingual' || viewMode === 'translation';

  const renderParagraph = (text: string, index: number, side: 'original' | 'translated') => {
    const isSelected = selectedIndex === index;
    return (
      <div
        key={`${side}-${index}`}
        role="button"
        tabIndex={0}
        aria-pressed={isSelected}
        onClick={() => handleParagraphClick(index)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleParagraphClick(index);
          }
        }}
        style={{ ...paragraphBaseStyle, ...(isSelected ? selectedStyle : null) }}
      >
        {text ? (
          <Text>{text}</Text>
        ) : (
          <Text type="secondary">—</Text>
        )}
      </div>
    );
  };

  const panelBodyStyle: CSSProperties = {
    height: PANEL_HEIGHT,
    overflowY: 'auto',
    padding: SPACING.sm,
  };

  if (rows.length === 0) {
    return <Empty description="暂无翻译内容" />;
  }

  return (
    <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
      {/* View switch (Req 11.35). */}
      <Segmented
        value={viewMode}
        onChange={(value) => setViewMode(value as DocumentViewMode)}
        options={[
          { label: '双语并排', value: 'bilingual' },
          { label: '仅原文', value: 'original' },
          { label: '仅翻译', value: 'translation' },
        ]}
      />

      <div
        style={{
          display: 'flex',
          gap: SPACING.md,
          flexDirection: 'row',
          flexWrap: 'wrap',
        }}
      >
        {showOriginal ? (
          <Card
            size="small"
            variant="outlined"
            style={{ flex: 1, minWidth: 280 }}
            styles={{ body: { padding: 0 } }}
            title={
              <Space size={SPACING.xs}>
                <Tag color="default">原文</Tag>
                <Text type="secondary">{sourceLabel}</Text>
              </Space>
            }
          >
            <div
              ref={originalRef}
              onScroll={handleScroll('original')}
              style={panelBodyStyle}
              aria-label="原文内容"
            >
              {rows.map((row, index) => renderParagraph(row.original, index, 'original'))}
            </div>
          </Card>
        ) : null}

        {showTranslated ? (
          <Card
            size="small"
            variant="outlined"
            style={{ flex: 1, minWidth: 280 }}
            styles={{ body: { padding: 0 } }}
            title={
              <Space size={SPACING.xs}>
                <Tag color="blue">译文</Tag>
                <Text type="secondary">{targetLabel}</Text>
              </Space>
            }
          >
            <div
              ref={translatedRef}
              onScroll={handleScroll('translated')}
              style={panelBodyStyle}
              aria-label="译文内容"
            >
              {rows.map((row, index) => renderParagraph(row.translated, index, 'translated'))}
            </div>
          </Card>
        ) : null}
      </div>

      <Text type="secondary">
        提示：点击任一段落可高亮两侧对应段落；双语并排模式下两栏滚动同步。
      </Text>
    </Space>
  );
}

export default BilingualDocumentView;
