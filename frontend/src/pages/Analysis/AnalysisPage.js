import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
/**
 * Data analysis page.
 *
 * The primary data-analysis workspace. It lets the User pick an uploaded data
 * file (or upload a new one), preview the first 10 rows (Req 2.2), review a data
 * quality summary (Req 2.6), run an Agent-driven multidimensional analysis with
 * a progress indicator (Req 3.7), and view the analysis results grouped by type
 * (descriptive statistics, correlation, outliers, trend, group comparison,
 * Req 3.1-3.5) together with the generated charts. It also displays the active
 * analysis dimensions, distinguishing system-generated from user-requested ones
 * and supporting removal of custom dimensions (Req 9.19-9.22).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Empty, Row, Select, Space, Typography } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { LoadingIndicator, PageContainer } from '../../components/Common';
import { ChartGrid } from '../../components/Charts';
import { ChatPanel } from '../../components/Chat';
import { FileUpload } from '../../components/Upload/FileUpload';
import { useConfirm } from '../../hooks/useConfirm';
import { useNotify } from '../../hooks/useNotify';
import { useResponsive } from '../../hooks/useResponsive';
import { analysisService } from '../../services/analysisService';
import { dataService } from '../../services/dataService';
import { ApiError } from '../../services/apiClient';
import { SPACING } from '../../theme/tokens';
import { formatFileSize } from '../../components/Upload/FileUpload';
import { DataPreviewTable } from './components/DataPreviewTable';
import { DataQualitySummary } from './components/DataQualitySummary';
import { AnalysisProgress } from './components/AnalysisProgress';
import { ResultSection, resultTypeLabel } from './components/ResultSection';
import { DimensionList } from './components/DimensionList';
import { ReportDownloadControl } from './components/ReportDownloadControl';
const { Text } = Typography;
/** Build the option label for a data file in the picker. */
function fileOptionLabel(file) {
    const parts = [file.original_filename, formatFileSize(file.file_size)];
    if (file.row_count != null && file.column_count != null) {
        parts.push(`${file.row_count} 行 × ${file.column_count} 列`);
    }
    return parts.join(' · ');
}
/**
 * Derive the system-generated dimensions from the analysis results.
 *
 * Each distinct `result_type` becomes a system dimension so the dimension list
 * reflects the default analyses the Agent performed (Req 9.19, 9.22).
 */
function deriveSystemDimensions(results) {
    const seen = new Set();
    const dims = [];
    for (const result of results) {
        if (seen.has(result.result_type)) {
            continue;
        }
        seen.add(result.result_type);
        dims.push({
            id: `system:${result.result_type}`,
            name: resultTypeLabel(result.result_type),
            dimension_type: 'system',
        });
    }
    return dims;
}
export function AnalysisPage() {
    const notify = useNotify();
    const confirm = useConfirm();
    const { isDesktop } = useResponsive();
    // File selection state.
    const [files, setFiles] = useState([]);
    const [filesLoading, setFilesLoading] = useState(true);
    const [selectedFileId, setSelectedFileId] = useState(null);
    // Preview + quality state for the selected file.
    const [preview, setPreview] = useState(null);
    const [quality, setQuality] = useState(null);
    const [fileDetailLoading, setFileDetailLoading] = useState(false);
    // Analysis state.
    const [analysisId, setAnalysisId] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [results, setResults] = useState([]);
    const [charts, setCharts] = useState([]);
    const [report, setReport] = useState(null);
    const [dimensions, setDimensions] = useState([]);
    const [removingDimId, setRemovingDimId] = useState(null);
    /** Load the user's data files. */
    const loadFiles = useCallback(async (autoSelectId) => {
        setFilesLoading(true);
        try {
            const response = await dataService.listFiles();
            setFiles(response.files);
            const firstFile = response.files[0];
            if (autoSelectId) {
                setSelectedFileId(autoSelectId);
            }
            else if (firstFile) {
                // Keep current selection if still present, else select the first file.
                setSelectedFileId((current) => current && response.files.some((f) => f.id === current)
                    ? current
                    : firstFile.id);
            }
        }
        catch (err) {
            notify.error('无法加载数据文件列表', err instanceof Error ? err.message : undefined);
        }
        finally {
            setFilesLoading(false);
        }
    }, [notify]);
    useEffect(() => {
        void loadFiles();
    }, [loadFiles]);
    /** Reset analysis artifacts whenever the selected file changes. */
    const resetAnalysis = useCallback(() => {
        setAnalysisId(null);
        setResults([]);
        setCharts([]);
        setReport(null);
        setDimensions([]);
    }, []);
    /** Load preview + quality for the selected file. */
    useEffect(() => {
        if (!selectedFileId) {
            setPreview(null);
            setQuality(null);
            return;
        }
        let cancelled = false;
        resetAnalysis();
        setFileDetailLoading(true);
        void (async () => {
            try {
                const [previewData, qualityData] = await Promise.all([
                    dataService.getPreview(selectedFileId),
                    dataService.getQuality(selectedFileId),
                ]);
                if (!cancelled) {
                    setPreview(previewData);
                    setQuality(qualityData);
                }
            }
            catch (err) {
                if (!cancelled) {
                    notify.error('无法加载数据预览或质量报告', err instanceof Error ? err.message : undefined);
                    setPreview(null);
                    setQuality(null);
                }
            }
            finally {
                if (!cancelled) {
                    setFileDetailLoading(false);
                }
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [selectedFileId, resetAnalysis, notify]);
    const selectedFile = useMemo(() => files.find((f) => f.id === selectedFileId) ?? null, [files, selectedFileId]);
    /** Apply a start/dimension response into local analysis state. */
    const applyStartResponse = useCallback((response) => {
        setAnalysisId(response.session.id);
        setResults(response.results);
        setCharts(response.charts);
        setReport(response.report ?? null);
        setDimensions(deriveSystemDimensions(response.results));
    }, []);
    /**
     * Append charts/results returned from the conversation to the dashboard.
     *
     * New charts and analysis results produced through the Chat_Interface are
     * added to the existing analysis dashboard (Req 9.13). Raw chat result
     * payloads are normalized into the dashboard's {@link AnalysisResult} shape.
     */
    const handleChatArtifacts = useCallback(({ charts: newCharts, analysisResults, }) => {
        if (newCharts.length > 0) {
            // ChartData is structurally identical to the dashboard Chart type.
            setCharts((current) => [...current, ...newCharts]);
        }
        if (analysisResults.length > 0) {
            const mapped = analysisResults.map((raw, index) => {
                const resultType = typeof raw.result_type === 'string' && raw.result_type ? raw.result_type : 'analysis';
                const resultData = raw.result_data && typeof raw.result_data === 'object' && !Array.isArray(raw.result_data)
                    ? raw.result_data
                    : Object.fromEntries(Object.entries(raw).filter(([key]) => key !== 'result_type'));
                return {
                    id: `chat:${Date.now()}:${index}`,
                    result_type: resultType,
                    result_data: resultData,
                };
            });
            setResults((current) => {
                const next = [...current, ...mapped];
                // Reflect any newly introduced result types in the dimension list.
                setDimensions(deriveSystemDimensions(next));
                return next;
            });
        }
    }, []);
    /** Start an Agent-driven analysis for the selected file. */
    const handleStartAnalysis = useCallback(async () => {
        if (!selectedFileId) {
            return;
        }
        setAnalyzing(true);
        try {
            const response = await analysisService.start(selectedFileId);
            applyStartResponse(response);
            notify.success('分析完成');
        }
        catch (err) {
            const message = err instanceof ApiError || err instanceof Error ? err.message : '请稍后重试。';
            notify.error('分析失败', message);
        }
        finally {
            setAnalyzing(false);
        }
    }, [selectedFileId, applyStartResponse, notify]);
    /** Remove a user-requested dimension (Req 9.20, 9.21). */
    const handleRemoveDimension = useCallback(async (dimension) => {
        if (!analysisId) {
            return;
        }
        const confirmed = await confirm({
            title: '移除分析维度',
            content: `确定要移除「${dimension.name}」维度吗？该维度的分析结果将从仪表盘中移除。`,
            danger: true,
        });
        if (!confirmed) {
            return;
        }
        setRemovingDimId(dimension.id);
        try {
            await analysisService.removeDimension(analysisId, dimension.id);
            setDimensions((current) => current.filter((d) => d.id !== dimension.id));
            // Refresh results/charts so the dashboard excludes the removed dimension.
            const [resultsData, chartsData] = await Promise.all([
                analysisService.results(analysisId),
                analysisService.charts(analysisId),
            ]);
            setResults(resultsData.results);
            setReport(resultsData.report ?? null);
            setCharts(chartsData.charts);
            notify.success('已移除分析维度');
        }
        catch (err) {
            notify.error('移除维度失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setRemovingDimId(null);
        }
    }, [analysisId, confirm, notify]);
    // Group results by type for sectioned display (Req 3.1-3.5).
    const hasResults = results.length > 0;
    // The analysis workspace content (left column).
    const analysisContent = (_jsxs(Space, { direction: "vertical", size: SPACING.lg, style: { width: '100%' }, children: [_jsxs(Row, { gutter: [SPACING.lg, SPACING.lg], children: [_jsx(Col, { xs: 24, lg: 14, children: _jsx(Card, { title: "\u9009\u62E9\u6570\u636E\u6587\u4EF6", variant: "outlined", children: filesLoading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u52A0\u8F7D\u6587\u4EF6\u5217\u8868\u2026", size: "default" })) : files.length > 0 ? (_jsx(Select, { style: { width: '100%' }, placeholder: "\u8BF7\u9009\u62E9\u4E00\u4E2A\u6570\u636E\u6587\u4EF6", value: selectedFileId ?? undefined, onChange: (value) => setSelectedFileId(value), options: files.map((file) => ({
                                    value: file.id,
                                    label: fileOptionLabel(file),
                                })), showSearch: true, optionFilterProp: "label" })) : (_jsx(Empty, { description: "\u6682\u65E0\u6570\u636E\u6587\u4EF6\uFF0C\u8BF7\u5148\u4E0A\u4F20\u4E00\u4E2A\u6587\u4EF6" })) }) }), _jsx(Col, { xs: 24, lg: 10, children: _jsx(Card, { title: "\u4E0A\u4F20\u65B0\u6587\u4EF6", variant: "outlined", children: _jsx(FileUpload, { onUploaded: (file) => {
                                    notify.info('文件已上传，正在刷新列表…');
                                    void loadFiles(file.id);
                                } }) }) })] }), selectedFile ? (_jsxs(_Fragment, { children: [_jsx(Card, { title: "\u6570\u636E\u9884\u89C8\uFF08\u524D 10 \u884C\uFF09", variant: "outlined", children: fileDetailLoading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u52A0\u8F7D\u6570\u636E\u9884\u89C8\u2026", size: "default" })) : preview ? (_jsx(DataPreviewTable, { preview: preview })) : (_jsx(Empty, { description: "\u65E0\u6CD5\u52A0\u8F7D\u6570\u636E\u9884\u89C8" })) }), _jsx(Card, { title: "\u6570\u636E\u8D28\u91CF\u6458\u8981", variant: "outlined", children: fileDetailLoading ? (_jsx(LoadingIndicator, { tip: "\u6B63\u5728\u52A0\u8F7D\u6570\u636E\u8D28\u91CF\u62A5\u544A\u2026", size: "default" })) : quality ? (_jsx(DataQualitySummary, { quality: quality })) : (_jsx(Empty, { description: "\u65E0\u6CD5\u52A0\u8F7D\u6570\u636E\u8D28\u91CF\u62A5\u544A" })) }), _jsx(Card, { title: "AI \u591A\u7EF4\u5EA6\u5206\u6790", variant: "outlined", children: _jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsxs(Space, { wrap: true, children: [_jsx(Button, { type: "primary", icon: _jsx(PlayCircleOutlined, {}), loading: analyzing, disabled: !selectedFileId || fileDetailLoading, onClick: () => void handleStartAnalysis(), children: hasResults ? '重新分析' : '开始分析' }), hasResults ? (_jsx(Text, { type: "secondary", children: "\u5206\u6790\u5DF2\u5B8C\u6210\uFF0C\u53EF\u5728\u4E0B\u65B9\u67E5\u770B\u7ED3\u679C\u4E0E\u56FE\u8868\u3002" })) : null] }), analyzing ? _jsx(AnalysisProgress, {}) : null] }) }), hasResults ? (_jsx(Card, { title: "\u5206\u6790\u7EF4\u5EA6", variant: "outlined", children: _jsx(DimensionList, { dimensions: dimensions, onRemove: (dimension) => void handleRemoveDimension(dimension), removingId: removingDimId }) })) : null, hasResults ? (_jsx(Card, { title: "\u5206\u6790\u7ED3\u679C", variant: "outlined", children: results.map((result) => (_jsx(ResultSection, { result: result }, result.id))) })) : null, hasResults ? (_jsx(Card, { title: "\u53EF\u89C6\u5316\u56FE\u8868", variant: "outlined", children: _jsx(ChartGrid, { charts: charts }) })) : null, hasResults && analysisId ? (_jsx(Card, { title: "\u5206\u6790\u62A5\u544A", variant: "outlined", children: _jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [report ? (_jsx(Text, { type: "secondary", children: `当前报告：${report.title}` })) : (_jsx(Text, { type: "secondary", children: "\u70B9\u51FB\u300C\u751F\u6210\u62A5\u544A\u300D\u4EE5\u751F\u6210\u7ED3\u6784\u5316\u5206\u6790\u62A5\u544A\uFF0C\u5E76\u53EF\u4E0B\u8F7D\u4E3A PDF \u6216 Word \u683C\u5F0F\u3002" })), _jsx(ReportDownloadControl, { analysisId: analysisId, report: report, onReportGenerated: setReport })] }) })) : null] })) : null] }));
    // Persistent chat panel (right column on desktop, stacked on tablet) (Req 9.1, 9.4).
    // Linked to the current analysis session once one has been started (Req 9.14).
    const chatPanel = (_jsx(ChatPanel, { analysisSessionId: analysisId ?? undefined, onArtifacts: handleChatArtifacts, height: isDesktop ? 'calc(100vh - 168px)' : 520 }));
    return (_jsx(PageContainer, { title: "\u6570\u636E\u5206\u6790", description: "\u9009\u62E9\u5DF2\u4E0A\u4F20\u7684\u6570\u636E\u6587\u4EF6\u6216\u4E0A\u4F20\u65B0\u6587\u4EF6\uFF0C\u7531 AI \u8FDB\u884C\u591A\u7EF4\u5EA6\u5206\u6790\u5E76\u751F\u6210\u53EF\u89C6\u5316\u7ED3\u679C\u3002", extra: _jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: () => void loadFiles(selectedFileId ?? undefined), disabled: filesLoading, children: "\u5237\u65B0\u6587\u4EF6" }), children: _jsxs(Row, { gutter: [SPACING.lg, SPACING.lg], wrap: true, children: [_jsx(Col, { xs: 24, xl: 16, children: analysisContent }), _jsx(Col, { xs: 24, xl: 8, children: isDesktop ? (_jsx("div", { style: { position: 'sticky', top: SPACING.lg }, children: chatPanel })) : (chatPanel) })] }) }));
}
export default AnalysisPage;
