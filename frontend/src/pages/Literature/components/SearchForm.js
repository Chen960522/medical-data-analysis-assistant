import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { Button, Checkbox, Collapse, DatePicker, Form, Input, Space, Tag, Typography, } from 'antd';
import { SearchOutlined, BulbOutlined } from '@ant-design/icons';
import { literatureService } from '../../../services/literatureService';
import { DATA_SOURCE_IDS, SOURCE_LABELS } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
const { RangePicker } = DatePicker;
/** Debounce delay for MeSH term suggestions (Req 10.20). */
const MESH_DEBOUNCE_MS = 350;
const SOURCE_OPTIONS = DATA_SOURCE_IDS.map((id) => ({
    label: SOURCE_LABELS[id],
    value: id,
}));
export function SearchForm({ onSearch, loading = false }) {
    const [form] = Form.useForm();
    const [keywords, setKeywords] = useState('');
    const [meshTerms, setMeshTerms] = useState([]);
    const debounceRef = useRef(undefined);
    const abortRef = useRef(null);
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
                }
                catch {
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
    const appendMeshTerm = useCallback((term) => {
        const current = form.getFieldValue('keywords');
        const existing = (current ?? '').trim();
        if (existing.toLowerCase().includes(term.toLowerCase())) {
            return;
        }
        const next = existing ? `${existing} ${term}` : term;
        form.setFieldsValue({ keywords: next });
        setKeywords(next);
    }, [form]);
    const handleFinish = useCallback((values) => {
        const [start, end] = values.dateRange ?? [];
        const criteria = {
            keywords: values.keywords.trim(),
            author: values.author?.trim() || undefined,
            journal: values.journal?.trim() || undefined,
            subject: values.subject?.trim() || undefined,
            date_from: start ? start.format('YYYY-MM-DD') : undefined,
            date_to: end ? end.format('YYYY-MM-DD') : undefined,
            sources: values.sources?.length ? values.sources : [...DATA_SOURCE_IDS],
        };
        onSearch(criteria);
    }, [onSearch]);
    const advancedItems = useMemo(() => [
        {
            key: 'advanced',
            label: '高级搜索筛选',
            children: (_jsxs(Space, { direction: "vertical", size: SPACING.sm, style: { width: '100%' }, children: [_jsx(Form.Item, { name: "author", label: "\u4F5C\u8005", style: { marginBottom: SPACING.sm }, children: _jsx(Input, { allowClear: true, placeholder: "\u6309\u4F5C\u8005\u59D3\u540D\u7B5B\u9009" }) }), _jsx(Form.Item, { name: "journal", label: "\u671F\u520A", style: { marginBottom: SPACING.sm }, children: _jsx(Input, { allowClear: true, placeholder: "\u6309\u671F\u520A\u540D\u79F0\u7B5B\u9009" }) }), _jsx(Form.Item, { name: "subject", label: "\u5B66\u79D1\u9886\u57DF", style: { marginBottom: SPACING.sm }, children: _jsx(Input, { allowClear: true, placeholder: "\u6309\u5B66\u79D1\u9886\u57DF\u7B5B\u9009" }) }), _jsx(Form.Item, { name: "dateRange", label: "\u53D1\u8868\u65F6\u95F4", style: { marginBottom: 0 }, children: _jsx(RangePicker, { style: { width: '100%' }, allowEmpty: [true, true] }) })] })),
        },
    ], []);
    return (_jsxs(Form, { form: form, layout: "vertical", initialValues: { keywords: '', sources: [...DATA_SOURCE_IDS] }, onFinish: handleFinish, children: [_jsx(Form.Item, { name: "keywords", label: "\u5173\u952E\u8BCD", rules: [{ required: true, message: '请输入检索关键词' }], style: { marginBottom: SPACING.sm }, children: _jsx(Input, { allowClear: true, size: "large", prefix: _jsx(SearchOutlined, {}), placeholder: "\u8F93\u5165\u4E2D\u6587\u6216\u82F1\u6587\u68C0\u7D22\u5173\u952E\u8BCD", onChange: (event) => setKeywords(event.target.value), onPressEnter: () => form.submit() }) }), meshTerms.length > 0 ? (_jsx("div", { style: { marginBottom: SPACING.md }, children: _jsxs(Space, { size: SPACING.xs, align: "center", wrap: true, children: [_jsxs(Text, { type: "secondary", children: [_jsx(BulbOutlined, {}), " MeSH \u672F\u8BED\u5EFA\u8BAE\uFF1A"] }), meshTerms.map((term) => (_jsx(Tag, { color: "blue", style: { cursor: 'pointer' }, onClick: () => appendMeshTerm(term), children: term }, term)))] }) })) : null, _jsx(Form.Item, { name: "sources", label: "\u6570\u636E\u6E90", rules: [{ required: true, message: '请至少选择一个数据源' }], style: { marginBottom: SPACING.md }, children: _jsx(Checkbox.Group, { options: SOURCE_OPTIONS }) }), _jsx(Collapse, { ghost: true, items: advancedItems, style: { marginBottom: SPACING.md } }), _jsx(Form.Item, { style: { marginBottom: 0 }, children: _jsx(Button, { type: "primary", htmlType: "submit", icon: _jsx(SearchOutlined, {}), loading: loading, block: true, children: "\u641C\u7D22\u6587\u732E" }) })] }));
}
export default SearchForm;
