import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { Highlight } from './Highlight';
const { Text, Paragraph, Link } = Typography;
/** Color the data-source tag distinctly per source (text label always shown). */
function sourceTagColor(source) {
    return source === 'PubMed' ? 'geekblue' : 'volcano';
}
export function ResultItem({ record, keywords, onOpenDetail, onSave }) {
    const preview = record.abstract_preview ?? record.abstract ?? '';
    const authors = record.authors.length > 0 ? record.authors.join('、') : '未知作者';
    return (_jsx(List.Item, { actions: [
            _jsx(Button, { type: "text", icon: _jsx(StarOutlined, {}), onClick: () => onSave(record), "aria-label": `收藏文献：${record.title}`, children: "\u6536\u85CF" }, "save"),
        ], children: _jsx(List.Item.Meta, { title: _jsx(Link, { onClick: () => onOpenDetail(record), style: { fontSize: 16 }, children: _jsx(Highlight, { text: record.title, terms: keywords }) }), description: _jsxs(Space, { direction: "vertical", size: SPACING.xs, style: { width: '100%' }, children: [_jsxs(Space, { size: SPACING.sm, wrap: true, children: [_jsx(Tag, { color: sourceTagColor(record.data_source), children: record.data_source }), _jsxs(Text, { type: "secondary", children: [_jsx(TeamOutlined, {}), " ", authors] }), record.journal ? (_jsxs(Text, { type: "secondary", children: [_jsx(BookOutlined, {}), " ", record.journal] })) : null, record.publication_date ? (_jsxs(Text, { type: "secondary", children: [_jsx(CalendarOutlined, {}), " ", record.publication_date] })) : null, record.citation_count != null ? (_jsxs(Text, { type: "secondary", children: ["\u88AB\u5F15 ", record.citation_count] })) : null] }), preview ? (_jsx(Paragraph, { style: { marginBottom: 0 }, ellipsis: { rows: 3 }, children: _jsx(Highlight, { text: preview, terms: keywords }) })) : null] }) }) }));
}
export default ResultItem;
