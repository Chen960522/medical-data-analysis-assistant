import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Literature search page.
 *
 * The Literature_Search_Module, accessible from the main navigation (Req 10.1).
 * It is organized into two tabs: 搜索 (search) and 我的收藏 (my collections).
 *
 * Search tab: a search form (keyword, advanced filters, data-source selector,
 * Req 10.2-10.8) with MeSH suggestions (Req 10.20); a results list with keyword
 * highlighting (Req 10.22, 10.23), per-source totals (Req 10.28), sorting
 * (Req 10.24), a client-side source filter (Req 10.25), and pagination
 * (default 20/page, Req 10.5). Clicking a result title opens the detail drawer
 * (Req 10.26) with a bilingual comparison toggle (Req 10.29-10.35) and a save
 * action (Req 10.36).
 *
 * Collections tab: lists, filters and searches the user's collections, supports
 * creating collections/folders, removing items and deleting collections
 * (Req 10.36-10.43).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Tabs } from 'antd';
import { SearchOutlined, StarOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/Common';
import { useNotify } from '../../hooks/useNotify';
import { literatureService } from '../../services/literatureService';
import { DATA_SOURCE_IDS, DEFAULT_PAGE_SIZE } from '../../types/literature';
import { SPACING } from '../../theme/tokens';
import { SearchForm } from './components/SearchForm';
import { ResultList } from './components/ResultList';
import { LiteratureDetail } from './components/LiteratureDetail';
import { SaveToCollectionModal } from './components/SaveToCollectionModal';
import { CollectionsView } from './components/CollectionsView';
/** Empty search response used before any search runs. */
const EMPTY_RESPONSE = {
    results: [],
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    total: 0,
    totals: {},
};
export function LiteraturePage() {
    const notify = useNotify();
    const notifyRef = useRef(notify);
    notifyRef.current = notify;
    const [activeTab, setActiveTab] = useState('search');
    // Search state. The latest criteria drives pagination/sort re-fetches.
    const [criteria, setCriteria] = useState(null);
    const [response, setResponse] = useState(EMPTY_RESPONSE);
    const [loading, setLoading] = useState(false);
    const [searched, setSearched] = useState(false);
    const [page, setPage] = useState(1);
    const [sortBy, setSortBy] = useState('relevance');
    const [sourceFilter, setSourceFilter] = useState('all');
    // Detail drawer + save modal state.
    const [detailRecord, setDetailRecord] = useState(null);
    const [detailOpen, setDetailOpen] = useState(false);
    const [saveRecord, setSaveRecord] = useState(null);
    const [saveOpen, setSaveOpen] = useState(false);
    // Collections (loaded for the save modal + reloaded on collection changes).
    const [collections, setCollections] = useState([]);
    const [collectionsReloadToken, setCollectionsReloadToken] = useState(0);
    const abortRef = useRef(null);
    /** Load collections for the save modal picker. */
    const loadCollections = useCallback(async () => {
        try {
            const result = await literatureService.listCollections();
            setCollections(result.collections);
        }
        catch {
            // Non-fatal: the save modal can still create a collection.
        }
    }, []);
    useEffect(() => {
        void loadCollections();
    }, [loadCollections, collectionsReloadToken]);
    /** Run a literature search with the given criteria/page/sort (Req 10.4). */
    const runSearch = useCallback(async (activeCriteria, targetPage, sort) => {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        setLoading(true);
        setSearched(true);
        try {
            const result = await literatureService.search({
                keywords: activeCriteria.keywords,
                author: activeCriteria.author,
                journal: activeCriteria.journal,
                subject: activeCriteria.subject,
                date_from: activeCriteria.date_from,
                date_to: activeCriteria.date_to,
                sources: activeCriteria.sources.length
                    ? activeCriteria.sources
                    : [...DATA_SOURCE_IDS],
                page: targetPage,
                page_size: DEFAULT_PAGE_SIZE,
                sort_by: sort,
            }, controller.signal);
            setResponse(result);
        }
        catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') {
                return;
            }
            notifyRef.current.error('文献检索失败', err instanceof Error ? err.message : undefined);
            setResponse(EMPTY_RESPONSE);
        }
        finally {
            setLoading(false);
        }
    }, []); // notify via notifyRef
    /** Submit a new search from the form (resets to page 1). */
    const handleSearch = useCallback((next) => {
        setCriteria(next);
        setPage(1);
        setSourceFilter('all');
        void runSearch(next, 1, sortBy);
    }, [runSearch, sortBy]);
    /** Change sort and re-fetch from page 1 (Req 10.24). */
    const handleSortChange = useCallback((next) => {
        setSortBy(next);
        if (criteria) {
            setPage(1);
            void runSearch(criteria, 1, next);
        }
    }, [criteria, runSearch]);
    /** Change page and re-fetch (Req 10.5). */
    const handlePageChange = useCallback((next) => {
        setPage(next);
        if (criteria) {
            void runSearch(criteria, next, sortBy);
        }
    }, [criteria, runSearch, sortBy]);
    // Clean up an in-flight search on unmount.
    useEffect(() => () => abortRef.current?.abort(), []);
    /** Open the detail drawer for a record (Req 10.26). */
    const handleOpenDetail = useCallback((record) => {
        setDetailRecord(record);
        setDetailOpen(true);
    }, []);
    /** Open the save-to-collection modal for a record (Req 10.36). */
    const handleSaveRequest = useCallback((record) => {
        setSaveRecord(record);
        setSaveOpen(true);
        void loadCollections();
    }, [loadCollections]);
    /** Called after a save / collection mutation succeeds. */
    const handleSaved = useCallback(() => {
        setCollectionsReloadToken((token) => token + 1);
    }, []);
    const searchTab = (_jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: SPACING.lg }, children: [_jsx(Card, { variant: "outlined", children: _jsx(SearchForm, { onSearch: handleSearch, loading: loading }) }), _jsx(Card, { variant: "outlined", children: _jsx(ResultList, { records: response.results, keywords: criteria?.keywords ?? '', loading: loading, searched: searched, page: page, pageSize: response.page_size || DEFAULT_PAGE_SIZE, total: response.total, totals: response.totals, sortBy: sortBy, sourceFilter: sourceFilter, onSortChange: handleSortChange, onSourceFilterChange: setSourceFilter, onPageChange: handlePageChange, onOpenDetail: handleOpenDetail, onSave: handleSaveRequest }) })] }));
    return (_jsxs(PageContainer, { title: "\u6587\u732E\u68C0\u7D22", description: "\u68C0\u7D22 CNKI \u4E0E PubMed \u533B\u5B66\u6587\u732E\uFF0C\u652F\u6301\u4E2D\u82F1\u6587\u53CC\u8BED\u5BF9\u6BD4\u67E5\u770B\u4E0E\u6587\u732E\u6536\u85CF\u7BA1\u7406\u3002", children: [_jsx(Tabs, { activeKey: activeTab, onChange: setActiveTab, items: [
                    {
                        key: 'search',
                        label: (_jsxs("span", { children: [_jsx(SearchOutlined, {}), " \u641C\u7D22"] })),
                        children: searchTab,
                    },
                    {
                        key: 'collections',
                        label: (_jsxs("span", { children: [_jsx(StarOutlined, {}), " \u6211\u7684\u6536\u85CF"] })),
                        children: _jsx(CollectionsView, { reloadToken: collectionsReloadToken }),
                    },
                ] }), _jsx(LiteratureDetail, { open: detailOpen, record: detailRecord, onClose: () => setDetailOpen(false), onSave: handleSaveRequest }), _jsx(SaveToCollectionModal, { open: saveOpen, record: saveRecord, collections: collections, onClose: () => setSaveOpen(false), onSaved: handleSaved })] }));
}
export default LiteraturePage;
