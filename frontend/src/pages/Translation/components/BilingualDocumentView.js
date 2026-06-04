import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { GEOMETRY, PALETTE, SPACING } from '../../../theme/tokens';
import { languageLabel } from '../../../types/translation';
const { Text } = Typography;
/** Fixed panel height so synchronized scrolling has a scrollable viewport. */
const PANEL_HEIGHT = 560;
const paragraphBaseStyle = {
    padding: SPACING.sm,
    borderRadius: GEOMETRY.borderRadius,
    marginBottom: SPACING.sm,
    cursor: 'pointer',
    transition: 'background-color 150ms ease',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
};
const selectedStyle = {
    backgroundColor: 'rgba(22, 119, 255, 0.12)',
    outline: `1px solid ${PALETTE.primary}`,
};
export function BilingualDocumentView({ originalParagraphs, translatedParagraphs, sourceLanguage, targetLanguage, }) {
    const [viewMode, setViewMode] = useState('bilingual');
    const [selectedIndex, setSelectedIndex] = useState(null);
    const originalRef = useRef(null);
    const translatedRef = useRef(null);
    // Guards against scroll feedback loops while syncing the two panels.
    const isSyncingRef = useRef(false);
    // Pair original and translated paragraphs by index (Req 11.31).
    const rows = useMemo(() => {
        const length = Math.max(originalParagraphs.length, translatedParagraphs.length);
        return Array.from({ length }, (_, index) => ({
            original: originalParagraphs[index] ?? '',
            translated: translatedParagraphs[index] ?? '',
        }));
    }, [originalParagraphs, translatedParagraphs]);
    /** Synchronize scroll position proportionally between panels (Req 11.34). */
    const handleScroll = (source) => () => {
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
    const handleParagraphClick = (index) => {
        setSelectedIndex((current) => (current === index ? null : index));
    };
    const sourceLabel = `原文（${languageLabel(sourceLanguage)}）`;
    const targetLabel = `译文（${languageLabel(targetLanguage)}）`;
    const showOriginal = viewMode === 'bilingual' || viewMode === 'original';
    const showTranslated = viewMode === 'bilingual' || viewMode === 'translation';
    const renderParagraph = (text, index, side) => {
        const isSelected = selectedIndex === index;
        return (_jsx("div", { role: "button", tabIndex: 0, "aria-pressed": isSelected, onClick: () => handleParagraphClick(index), onKeyDown: (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleParagraphClick(index);
                }
            }, style: { ...paragraphBaseStyle, ...(isSelected ? selectedStyle : null) }, children: text ? (_jsx(Text, { children: text })) : (_jsx(Text, { type: "secondary", children: "\u2014" })) }, `${side}-${index}`));
    };
    const panelBodyStyle = {
        height: PANEL_HEIGHT,
        overflowY: 'auto',
        padding: SPACING.sm,
    };
    if (rows.length === 0) {
        return _jsx(Empty, { description: "\u6682\u65E0\u7FFB\u8BD1\u5185\u5BB9" });
    }
    return (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsx(Segmented, { value: viewMode, onChange: (value) => setViewMode(value), options: [
                    { label: '双语并排', value: 'bilingual' },
                    { label: '仅原文', value: 'original' },
                    { label: '仅翻译', value: 'translation' },
                ] }), _jsxs("div", { style: {
                    display: 'flex',
                    gap: SPACING.md,
                    flexDirection: 'row',
                    flexWrap: 'wrap',
                }, children: [showOriginal ? (_jsx(Card, { size: "small", variant: "outlined", style: { flex: 1, minWidth: 280 }, styles: { body: { padding: 0 } }, title: _jsxs(Space, { size: SPACING.xs, children: [_jsx(Tag, { color: "default", children: "\u539F\u6587" }), _jsx(Text, { type: "secondary", children: sourceLabel })] }), children: _jsx("div", { ref: originalRef, onScroll: handleScroll('original'), style: panelBodyStyle, "aria-label": "\u539F\u6587\u5185\u5BB9", children: rows.map((row, index) => renderParagraph(row.original, index, 'original')) }) })) : null, showTranslated ? (_jsx(Card, { size: "small", variant: "outlined", style: { flex: 1, minWidth: 280 }, styles: { body: { padding: 0 } }, title: _jsxs(Space, { size: SPACING.xs, children: [_jsx(Tag, { color: "blue", children: "\u8BD1\u6587" }), _jsx(Text, { type: "secondary", children: targetLabel })] }), children: _jsx("div", { ref: translatedRef, onScroll: handleScroll('translated'), style: panelBodyStyle, "aria-label": "\u8BD1\u6587\u5185\u5BB9", children: rows.map((row, index) => renderParagraph(row.translated, index, 'translated')) }) })) : null] }), _jsx(Text, { type: "secondary", children: "\u63D0\u793A\uFF1A\u70B9\u51FB\u4EFB\u4E00\u6BB5\u843D\u53EF\u9AD8\u4EAE\u4E24\u4FA7\u5BF9\u5E94\u6BB5\u843D\uFF1B\u53CC\u8BED\u5E76\u6392\u6A21\u5F0F\u4E0B\u4E24\u680F\u6EDA\u52A8\u540C\u6B65\u3002" })] }));
}
export default BilingualDocumentView;
