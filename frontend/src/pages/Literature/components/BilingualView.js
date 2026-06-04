import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
const { Title, Paragraph, Text } = Typography;
/** Human label for a language code. */
const LANG_LABEL = { zh: '中文', en: '英文' };
/** Split text into paragraphs on blank lines / newlines for alignment. */
function toParagraphs(text) {
    if (!text) {
        return [];
    }
    const parts = text
        .split(/\n{1,}/)
        .map((part) => part.trim())
        .filter((part) => part.length > 0);
    return parts.length > 0 ? parts : [text.trim()];
}
export function BilingualView({ dataSource, originalTitle, originalAbstract, content, loading, error, }) {
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
    return (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [error ? (_jsx(Alert, { type: "error", showIcon: true, message: "\u7FFB\u8BD1\u6682\u65F6\u4E0D\u53EF\u7528", description: `${error} 下方仍展示原文内容。` })) : null, _jsxs(Row, { gutter: [SPACING.md, SPACING.md], children: [_jsx(Col, { xs: 24, md: 12, children: _jsxs(Card, { size: "small", variant: "outlined", title: _jsxs(Space, { size: SPACING.xs, children: [_jsx(Tag, { color: "default", children: "\u539F\u6587" }), _jsx(Text, { type: "secondary", children: originalLabel })] }), style: { height: '100%' }, children: [_jsx(Title, { level: 5, style: { marginTop: 0 }, children: originalTitle }), rows.length > 0 ? (rows.map((row, index) => (_jsx(Paragraph, { style: { marginBottom: SPACING.sm }, children: row.original }, `o-${index}`)))) : (_jsx(Text, { type: "secondary", children: "\u65E0\u6458\u8981\u5185\u5BB9" }))] }) }), _jsx(Col, { xs: 24, md: 12, children: _jsx(Card, { size: "small", variant: "outlined", title: _jsxs(Space, { size: SPACING.xs, children: [_jsx(Tag, { color: "blue", children: "\u8BD1\u6587" }), _jsx(Text, { type: "secondary", children: translatedLabel })] }), style: { height: '100%' }, children: loading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u7FFB\u8BD1\u2026", size: "default" })) : content ? (_jsxs(_Fragment, { children: [_jsx(Title, { level: 5, style: { marginTop: 0 }, children: content.translated_title ?? '—' }), rows.length > 0 ? (rows.map((row, index) => (_jsx(Paragraph, { style: { marginBottom: SPACING.sm }, children: row.translated || '—' }, `t-${index}`)))) : (_jsx(Text, { type: "secondary", children: "\u65E0\u8BD1\u6587\u5185\u5BB9" }))] })) : (_jsx(Text, { type: "secondary", children: "\u7FFB\u8BD1\u4E0D\u53EF\u7528" })) }) })] })] }));
}
export default BilingualView;
