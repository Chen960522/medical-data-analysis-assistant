import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
import { Button, Descriptions, Divider, Drawer, Segmented, Space, Tag, Typography, } from 'antd';
import { StarOutlined, TranslationOutlined } from '@ant-design/icons';
import { useNotify } from '../../../hooks/useNotify';
import { literatureService } from '../../../services/literatureService';
import { SOURCE_LABELS } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';
import { BilingualView } from './BilingualView';
const { Title, Paragraph, Text } = Typography;
/** Map a canonical data-source label back to its lowercase identifier. */
function toSourceId(dataSource) {
    return dataSource === SOURCE_LABELS.pubmed ? 'pubmed' : 'cnki';
}
export function LiteratureDetail({ open, record, onClose, onSave }) {
    const notify = useNotify();
    const [mode, setMode] = useState('detail');
    const [detail, setDetail] = useState(record);
    const [bilingual, setBilingual] = useState(null);
    const [translating, setTranslating] = useState(false);
    const [translateError, setTranslateError] = useState(null);
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
                const full = await literatureService.getDetail(record.external_id, toSourceId(record.data_source), controller.signal);
                setDetail(full);
            }
            catch {
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
            const result = await literatureService.translate(detail.external_id ?? detail.title, {
                title: detail.title,
                abstract: detail.abstract ?? undefined,
                source: toSourceId(detail.data_source),
            });
            setBilingual(result);
        }
        catch (err) {
            setTranslateError(err instanceof Error ? err.message : '请稍后重试。');
        }
        finally {
            setTranslating(false);
        }
    }, [detail, bilingual, translating]);
    const current = detail ?? record;
    return (_jsx(Drawer, { title: "\u6587\u732E\u8BE6\u60C5", open: open, onClose: onClose, width: 760, extra: current ? (_jsxs(Space, { children: [_jsx(Button, { icon: _jsx(TranslationOutlined, {}), type: mode === 'bilingual' ? 'primary' : 'default', onClick: () => void handleToggleBilingual(), children: "\u53CC\u8BED\u5BF9\u6BD4" }), _jsx(Button, { icon: _jsx(StarOutlined, {}), onClick: () => {
                        onSave(current);
                        notify.info('请选择收藏夹以保存该文献');
                    }, children: "\u6536\u85CF" })] })) : null, children: current ? (_jsxs(_Fragment, { children: [_jsx(Segmented, { value: mode, onChange: (value) => {
                        const next = value;
                        if (next === 'bilingual') {
                            void handleToggleBilingual();
                        }
                        else {
                            setMode('detail');
                        }
                    }, options: [
                        { label: '详情', value: 'detail' },
                        { label: '双语对比', value: 'bilingual' },
                    ], style: { marginBottom: SPACING.md } }), mode === 'detail' ? (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsx(Title, { level: 4, style: { marginBottom: 0 }, children: current.title }), _jsxs(Descriptions, { column: 1, size: "small", bordered: true, children: [_jsx(Descriptions.Item, { label: "\u6570\u636E\u6E90", children: _jsx(Tag, { color: current.data_source === SOURCE_LABELS.pubmed ? 'geekblue' : 'volcano', children: current.data_source }) }), _jsx(Descriptions.Item, { label: "\u4F5C\u8005", children: current.authors.length > 0 ? current.authors.join('、') : '未知作者' }), current.journal ? (_jsx(Descriptions.Item, { label: "\u671F\u520A", children: current.journal })) : null, current.publication_date ? (_jsx(Descriptions.Item, { label: "\u53D1\u8868\u65F6\u95F4", children: current.publication_date })) : null, current.doi ? _jsx(Descriptions.Item, { label: "DOI", children: current.doi }) : null, current.external_id ? (_jsx(Descriptions.Item, { label: "\u6807\u8BC6", children: current.external_id })) : null, current.citation_count != null ? (_jsx(Descriptions.Item, { label: "\u88AB\u5F15\u6B21\u6570", children: current.citation_count })) : null] }), current.keywords.length > 0 ? (_jsxs("div", { children: [_jsx(Text, { strong: true, children: "\u5173\u952E\u8BCD\uFF1A" }), _jsx(Space, { size: SPACING.xs, wrap: true, style: { marginTop: SPACING.xs }, children: current.keywords.map((keyword) => (_jsx(Tag, { children: keyword }, keyword))) })] })) : null, _jsx(Divider, { style: { margin: `${SPACING.sm}px 0` } }), _jsxs("div", { children: [_jsx(Text, { strong: true, children: "\u6458\u8981" }), _jsx(Paragraph, { style: { marginTop: SPACING.xs }, children: current.abstract ?? '暂无摘要' })] })] })) : (_jsx(BilingualView, { dataSource: current.data_source, originalTitle: current.title, originalAbstract: current.abstract, content: bilingual, loading: translating, error: translateError }))] })) : null }));
}
export default LiteratureDetail;
