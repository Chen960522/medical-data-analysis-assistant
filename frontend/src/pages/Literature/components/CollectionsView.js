import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
/**
 * Literature collections view (我的收藏).
 *
 * Lists the user's collections (newest first, Req 10.38), each showing its
 * folders and saved items grouped by folder. Supports creating collections and
 * folders (Req 10.36, 10.39), filtering items by data source (Req 10.40),
 * searching within collections by title/keyword (Req 10.42), removing items
 * (Req 10.41) and deleting collections (with confirmation).
 */
import { useCallback, useRef, useEffect, useMemo, useState } from 'react';
import { Button, Card, Collapse, Empty, Input, List, Segmented, Space, Tag, Typography, } from 'antd';
import { DeleteOutlined, FolderOutlined, PlusOutlined, ReloadOutlined, } from '@ant-design/icons';
import { LoadingIndicator } from '../../../components/Common';
import { useConfirm } from '../../../hooks/useConfirm';
import { useNotify } from '../../../hooks/useNotify';
import { literatureService } from '../../../services/literatureService';
import { SPACING } from '../../../theme/tokens';
const { Text, Paragraph, Link } = Typography;
/** Tag color for a saved item's source label (lower/upper tolerated). */
function itemSourceColor(source) {
    return source.toLowerCase() === 'pubmed' ? 'geekblue' : 'volcano';
}
export function CollectionsView({ reloadToken = 0 }) {
    const notify = useNotify();
    const notifyRef = useRef(notify);
    notifyRef.current = notify;
    const confirm = useConfirm();
    const confirmRef = useRef(confirm);
    confirmRef.current = confirm;
    const [collections, setCollections] = useState([]);
    const [loading, setLoading] = useState(true);
    const [sourceFilter, setSourceFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [creating, setCreating] = useState(false);
    const [newCollectionName, setNewCollectionName] = useState('');
    /** Load collections applying the active source/search filters (Req 10.40, 10.42). */
    const loadCollections = useCallback(async () => {
        setLoading(true);
        try {
            const response = await literatureService.listCollections({
                source: sourceFilter === 'all' ? undefined : sourceFilter,
                q: search.trim() || undefined,
            });
            setCollections(response.collections);
        }
        catch (err) {
            notifyRef.current.error('无法加载文献收藏', err instanceof Error ? err.message : undefined);
        }
        finally {
            setLoading(false);
        }
    }, [sourceFilter, search]); // notify via notifyRef
    useEffect(() => {
        void loadCollections();
    }, [loadCollections, reloadToken]);
    /** Create a new (empty) collection (Req 10.36). */
    const handleCreateCollection = useCallback(async () => {
        const name = newCollectionName.trim();
        if (!name) {
            return;
        }
        setCreating(true);
        try {
            await literatureService.createCollection({ name });
            notifyRef.current.success('收藏夹已创建');
            setNewCollectionName('');
            await loadCollections();
        }
        catch (err) {
            notifyRef.current.error('创建收藏夹失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setCreating(false);
        }
    }, [newCollectionName, notify, loadCollections]);
    /** Delete a collection after confirmation (Req 10.41). */
    const handleDeleteCollection = useCallback(async (collection) => {
        const confirmed = await confirmRef.current({
            title: '删除收藏夹',
            content: `确定要删除「${collection.name}」吗？其中的所有文件夹和收藏文献都将被移除。`,
            danger: true,
        });
        if (!confirmed) {
            return;
        }
        try {
            await literatureService.deleteCollection(collection.id);
            notifyRef.current.success('收藏夹已删除');
            await loadCollections();
        }
        catch (err) {
            notifyRef.current.error('删除收藏夹失败', err instanceof Error ? err.message : undefined);
        }
    }, [loadCollections]); // confirm+notify via refs
    /** Remove a saved item from its collection (Req 10.41). */
    const handleRemoveItem = useCallback(async (collection, item) => {
        const confirmed = await confirmRef.current({
            title: '移除收藏',
            content: `确定要从「${collection.name}」中移除该文献吗？`,
            danger: true,
        });
        if (!confirmed) {
            return;
        }
        try {
            await literatureService.removeItem(collection.id, item.id);
            notifyRef.current.success('已移除收藏');
            await loadCollections();
        }
        catch (err) {
            notifyRef.current.error('移除失败', err instanceof Error ? err.message : undefined);
        }
    }, [loadCollections]); // confirm+notify via refs
    const totalItems = useMemo(() => collections.reduce((sum, collection) => sum + collection.items.length, 0), [collections]);
    /** Render the saved-item list, grouped by folder then unfiled. */
    const renderItems = (collection) => {
        if (collection.items.length === 0) {
            return _jsx(Empty, { image: Empty.PRESENTED_IMAGE_SIMPLE, description: "\u8BE5\u6536\u85CF\u5939\u6682\u65E0\u6587\u732E" });
        }
        const folderName = new Map(collection.folders.map((f) => [f.id, f.name]));
        const grouped = new Map();
        for (const item of collection.items) {
            const key = item.folder_id ?? '__unfiled__';
            const list = grouped.get(key) ?? [];
            list.push(item);
            grouped.set(key, list);
        }
        const renderItemList = (items) => (_jsx(List, { size: "small", dataSource: items, renderItem: (item) => (_jsx(List.Item, { actions: [
                    _jsx(Button, { type: "text", danger: true, size: "small", icon: _jsx(DeleteOutlined, {}), onClick: () => void handleRemoveItem(collection, item), "aria-label": `移除收藏：${item.title}` }, "remove"),
                ], children: _jsx(List.Item.Meta, { title: _jsxs(Space, { size: SPACING.xs, wrap: true, children: [_jsx(Tag, { color: itemSourceColor(item.source), children: item.source.toUpperCase() }), item.doi ? (_jsx(Link, { href: `https://doi.org/${item.doi}`, target: "_blank", rel: "noreferrer", children: item.title })) : (_jsx(Text, { children: item.title }))] }), description: _jsxs(Space, { direction: "vertical", size: 0, style: { width: '100%' }, children: [_jsx(Text, { type: "secondary", children: item.authors || '未知作者' }), item.journal || item.publication_date ? (_jsx(Text, { type: "secondary", children: [item.journal, item.publication_date].filter(Boolean).join(' · ') })) : null, item.abstract ? (_jsx(Paragraph, { type: "secondary", ellipsis: { rows: 2 }, style: { marginBottom: 0 }, children: item.abstract })) : null] }) }) })) }));
        return (_jsx(Space, { direction: "vertical", size: SPACING.sm, style: { width: '100%' }, children: [...grouped.entries()].map(([key, items]) => (_jsxs("div", { children: [key !== '__unfiled__' ? (_jsxs(Text, { strong: true, children: [_jsx(FolderOutlined, {}), " ", folderName.get(key) ?? '文件夹'] })) : grouped.size > 1 ? (_jsx(Text, { strong: true, children: "\u672A\u5206\u7C7B" })) : null, renderItemList(items)] }, key))) }));
    };
    return (_jsxs(Space, { direction: "vertical", size: SPACING.lg, style: { width: '100%' }, children: [_jsx(Card, { variant: "outlined", children: _jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsxs(Space, { wrap: true, children: [_jsxs(Space.Compact, { children: [_jsx(Input, { value: newCollectionName, onChange: (event) => setNewCollectionName(event.target.value), placeholder: "\u65B0\u5EFA\u6536\u85CF\u5939\u540D\u79F0", onPressEnter: () => void handleCreateCollection(), style: { width: 220 } }), _jsx(Button, { type: "primary", icon: _jsx(PlusOutlined, {}), loading: creating, disabled: !newCollectionName.trim(), onClick: () => void handleCreateCollection(), children: "\u65B0\u5EFA\u6536\u85CF\u5939" })] }), _jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: () => void loadCollections(), children: "\u5237\u65B0" })] }), _jsxs(Space, { size: SPACING.md, wrap: true, children: [_jsx(Input.Search, { allowClear: true, value: search, onChange: (event) => setSearch(event.target.value), onSearch: () => void loadCollections(), placeholder: "\u6309\u6807\u9898\u6216\u5173\u952E\u8BCD\u641C\u7D22\u6536\u85CF", style: { width: 280 } }), _jsxs(Space, { size: SPACING.xs, children: [_jsx(Text, { type: "secondary", children: "\u6570\u636E\u6E90\uFF1A" }), _jsx(Segmented, { value: sourceFilter, onChange: (value) => setSourceFilter(value), options: [
                                                { label: '全部', value: 'all' },
                                                { label: 'CNKI', value: 'cnki' },
                                                { label: 'PubMed', value: 'pubmed' },
                                            ] })] })] })] }) }), loading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u52A0\u8F7D\u6587\u732E\u6536\u85CF\u2026" })) : collections.length === 0 ? (_jsx(Empty, { description: "\u6682\u65E0\u6536\u85CF\u5939\uFF0C\u8BF7\u5148\u65B0\u5EFA\u4E00\u4E2A\u6536\u85CF\u5939\u5E76\u4ECE\u641C\u7D22\u7ED3\u679C\u4E2D\u6536\u85CF\u6587\u732E" })) : (_jsxs(_Fragment, { children: [_jsxs(Text, { type: "secondary", children: ["\u5171 ", collections.length, " \u4E2A\u6536\u85CF\u5939 \u00B7 ", totalItems, " \u7BC7\u6587\u732E"] }), _jsx(Collapse, { defaultActiveKey: collections.map((c) => c.id), items: collections.map((collection) => ({
                            key: collection.id,
                            label: (_jsxs(Space, { children: [_jsx(Text, { strong: true, children: collection.name }), _jsxs(Tag, { children: [collection.items.length, " \u7BC7"] })] })),
                            extra: (_jsx(Button, { type: "text", danger: true, size: "small", icon: _jsx(DeleteOutlined, {}), onClick: (event) => {
                                    event.stopPropagation();
                                    void handleDeleteCollection(collection);
                                }, "aria-label": `删除收藏夹：${collection.name}` })),
                            children: renderItems(collection),
                        })) })] }))] }));
}
export default CollectionsView;
