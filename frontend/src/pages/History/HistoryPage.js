import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
/**
 * Analysis history management page (Req 6.1-6.5).
 *
 * Lists all of the authenticated user's completed analysis sessions, newest
 * first (Req 6.1, 6.2). Selecting a historical analysis fetches and displays its
 * complete results, charts, and report (Req 6.3); deleting a record prompts a
 * confirmation dialog before permanently removing it and its associated data
 * (Req 6.4).
 *
 * Note: actual report file download (PDF/Word) is implemented separately in
 * task 13.2 — here a generated report is surfaced by title only.
 */
import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Space, Typography } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';
import { LoadingIndicator, PageContainer } from '../../components/Common';
import { ChartGrid } from '../../components/Charts';
import { useConfirm } from '../../hooks/useConfirm';
import { useNotify } from '../../hooks/useNotify';
import { analysisService } from '../../services/analysisService';
import { SPACING } from '../../theme/tokens';
import { AnalysisHistoryList } from './components/AnalysisHistoryList';
import { ResultSection } from '../Analysis/components/ResultSection';
const { Text } = Typography;
export function HistoryPage() {
    const notify = useNotify();
    const confirm = useConfirm();
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    // Selected session + its loaded results/charts/report (Req 6.3).
    const [selected, setSelected] = useState(null);
    const [results, setResults] = useState([]);
    const [charts, setCharts] = useState([]);
    const [report, setReport] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    /** Load the analysis history, newest first (Req 6.1, 6.2). */
    const loadHistory = useCallback(async () => {
        setLoading(true);
        try {
            const response = await analysisService.history();
            setSessions(response.sessions);
        }
        catch (err) {
            notify.error('加载分析历史失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setLoading(false);
        }
    }, [notify]);
    useEffect(() => {
        void loadHistory();
    }, [loadHistory]);
    /** Open a historical analysis and load its full results, charts, report (Req 6.3). */
    const handleOpen = useCallback(async (session) => {
        setSelected(session);
        setResults([]);
        setCharts([]);
        setReport(null);
        setDetailLoading(true);
        try {
            const [resultsData, chartsData] = await Promise.all([
                analysisService.results(session.id),
                analysisService.charts(session.id),
            ]);
            setResults(resultsData.results);
            setReport(resultsData.report ?? null);
            setCharts(chartsData.charts);
        }
        catch (err) {
            notify.error('加载分析详情失败', err instanceof Error ? err.message : undefined);
            setSelected(null);
        }
        finally {
            setDetailLoading(false);
        }
    }, [notify]);
    /** Delete an analysis record after confirmation (Req 6.4). */
    const handleDelete = useCallback(async (session) => {
        const confirmed = await confirm({
            title: '删除分析记录',
            content: `确定要删除该分析记录（${session.id.slice(0, 8)}）吗？该操作将一并删除其分析结果、图表与报告，且不可恢复。`,
            danger: true,
        });
        if (!confirmed) {
            return;
        }
        setDeletingId(session.id);
        try {
            await analysisService.remove(session.id);
            notify.success('分析记录已删除');
            setSessions((prev) => prev.filter((s) => s.id !== session.id));
            if (selected?.id === session.id) {
                setSelected(null);
                setResults([]);
                setCharts([]);
                setReport(null);
            }
        }
        catch (err) {
            notify.error('删除失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setDeletingId(null);
        }
    }, [confirm, notify, selected]);
    const handleBack = useCallback(() => {
        setSelected(null);
        setResults([]);
        setCharts([]);
        setReport(null);
    }, []);
    const hasResults = results.length > 0;
    return (_jsx(PageContainer, { title: "\u5206\u6790\u5386\u53F2", description: "\u67E5\u770B\u5E76\u7BA1\u7406\u5386\u53F2\u5206\u6790\u8BB0\u5F55\uFF0C\u53EF\u6309\u65E5\u671F\u964D\u5E8F\u6D4F\u89C8\u3001\u67E5\u770B\u5B8C\u6574\u5206\u6790\u7ED3\u679C\u4E0E\u56FE\u8868\uFF0C\u6216\u5220\u9664\u4E0D\u518D\u9700\u8981\u7684\u8BB0\u5F55\u3002", extra: !selected ? (_jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: () => void loadHistory(), loading: loading, children: "\u5237\u65B0" })) : undefined, children: selected ? (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsxs(Space, { size: SPACING.sm, wrap: true, align: "center", children: [_jsx(Button, { icon: _jsx(ArrowLeftOutlined, {}), onClick: handleBack, children: "\u8FD4\u56DE\u5217\u8868" }), _jsx(Text, { strong: true, children: "\u5206\u6790\u7F16\u53F7\uFF1A" }), _jsx(Text, { code: true, children: selected.id.slice(0, 8) })] }), detailLoading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u52A0\u8F7D\u5206\u6790\u8BE6\u60C5\u2026" })) : (_jsxs(_Fragment, { children: [_jsx(Card, { title: "\u5206\u6790\u7ED3\u679C", variant: "outlined", children: hasResults ? (results.map((result) => _jsx(ResultSection, { result: result }, result.id))) : (_jsx(Empty, { description: "\u6682\u65E0\u5206\u6790\u7ED3\u679C" })) }), _jsx(Card, { title: "\u53EF\u89C6\u5316\u56FE\u8868", variant: "outlined", children: charts.length > 0 ? (_jsx(ChartGrid, { charts: charts })) : (_jsx(Empty, { description: "\u6682\u65E0\u53EF\u89C6\u5316\u56FE\u8868" })) }), report ? (_jsx(Alert, { type: "info", showIcon: true, message: `已生成分析报告：${report.title}`, description: "\u53EF\u5728\u62A5\u544A\u4E0B\u8F7D\u5165\u53E3\u4E2D\u5BFC\u51FA\u5B8C\u6574\u62A5\u544A\uFF08PDF/Word\uFF09\u3002" })) : null] }))] })) : (_jsx(Card, { variant: "outlined", children: _jsx(AnalysisHistoryList, { sessions: sessions, loading: loading, deletingId: deletingId, onOpen: (session) => void handleOpen(session), onDelete: (session) => void handleDelete(session) }) })) }));
}
export default HistoryPage;
