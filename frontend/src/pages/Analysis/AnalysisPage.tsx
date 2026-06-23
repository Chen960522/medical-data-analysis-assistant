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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Col, Empty, Row, Select, Space, Typography } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';

import { LoadingIndicator, PageContainer } from '../../components/Common';
import { ChartGrid } from '../../components/Charts';
import type { ChartData } from '../../components/Charts';
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
import type { DataFile, DataPreviewResponse, DataQualityResponse } from '../../types/data';
import type {
  AnalysisResult,
  Chart,
  Dimension,
  Report,
  StartAnalysisResponse,
} from '../../types/analysis';

import { DataPreviewTable } from './components/DataPreviewTable';
import { DataQualitySummary } from './components/DataQualitySummary';
import { AnalysisProgress } from './components/AnalysisProgress';
import { ResultSection, resultTypeLabel } from './components/ResultSection';
import { DimensionList } from './components/DimensionList';
import { ReportDownloadControl } from './components/ReportDownloadControl';

const { Text } = Typography;

/** Build the option label for a data file in the picker. */
function fileOptionLabel(file: DataFile): string {
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
function deriveSystemDimensions(results: AnalysisResult[]): Dimension[] {
  const seen = new Set<string>();
  const dims: Dimension[] = [];
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
  // Stable ref so useCallback deps don't trigger infinite re-renders.
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const confirm = useConfirm();
  const confirmRef = useRef(confirm);
  confirmRef.current = confirm;
  const { isDesktop } = useResponsive();

  // File selection state.
  const [files, setFiles] = useState<DataFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  // Preview + quality state for the selected file.
  const [preview, setPreview] = useState<DataPreviewResponse | null>(null);
  const [quality, setQuality] = useState<DataQualityResponse | null>(null);
  const [fileDetailLoading, setFileDetailLoading] = useState(false);

  // Analysis state.
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [removingDimId, setRemovingDimId] = useState<string | null>(null);

  /** Load the user's data files. */
  const loadFiles = useCallback(
    async (autoSelectId?: string) => {
      setFilesLoading(true);
      try {
        const response = await dataService.listFiles();
        setFiles(response.files);
        const firstFile = response.files[0];
        if (autoSelectId) {
          setSelectedFileId(autoSelectId);
        } else if (firstFile) {
          // Keep current selection if still present, else select the first file.
          setSelectedFileId((current) =>
            current && response.files.some((f) => f.id === current)
              ? current
              : firstFile.id,
          );
        }
      } catch (err) {
        notifyRef.current.error('无法加载数据文件列表', err instanceof Error ? err.message : undefined);
      } finally {
        setFilesLoading(false);
      }
    },
    [],
  );

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
      } catch (err) {
        if (!cancelled) {
          notifyRef.current.error('无法加载数据预览或质量报告', err instanceof Error ? err.message : undefined);
          setPreview(null);
          setQuality(null);
        }
      } finally {
        if (!cancelled) {
          setFileDetailLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedFileId, resetAnalysis]);

  const selectedFile = useMemo(
    () => files.find((f) => f.id === selectedFileId) ?? null,
    [files, selectedFileId],
  );

  /** Apply a start/dimension response into local analysis state. */
  const applyStartResponse = useCallback((response: StartAnalysisResponse) => {
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
  const handleChatArtifacts = useCallback(
    ({
      charts: newCharts,
      analysisResults,
    }: {
      charts: ChartData[];
      analysisResults: Record<string, unknown>[];
    }) => {
      if (newCharts.length > 0) {
        // ChartData is structurally identical to the dashboard Chart type.
        setCharts((current) => [...current, ...(newCharts as Chart[])]);
      }
      if (analysisResults.length > 0) {
        const mapped: AnalysisResult[] = analysisResults.map((raw, index) => {
          const resultType =
            typeof raw.result_type === 'string' && raw.result_type ? raw.result_type : 'analysis';
          const resultData =
            raw.result_data && typeof raw.result_data === 'object' && !Array.isArray(raw.result_data)
              ? (raw.result_data as Record<string, unknown>)
              : (Object.fromEntries(
                  Object.entries(raw).filter(([key]) => key !== 'result_type'),
                ) as Record<string, unknown>);
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
    },
    [],
  );

  /** Start an Agent-driven analysis for the selected file. */
  const handleStartAnalysis = useCallback(async () => {
    if (!selectedFileId) {
      return;
    }
    setAnalyzing(true);
    try {
      const response = await analysisService.start(selectedFileId);
      applyStartResponse(response);
      notifyRef.current.success('分析完成');
    } catch (err) {
      const message =
        err instanceof ApiError || err instanceof Error ? err.message : '请稍后重试。';
      notifyRef.current.error('分析失败', message);
    } finally {
      setAnalyzing(false);
    }
  }, [selectedFileId, applyStartResponse]);

  /** Remove a user-requested dimension (Req 9.20, 9.21). */
  const handleRemoveDimension = useCallback(
    async (dimension: Dimension) => {
      if (!analysisId) {
        return;
      }
      const confirmed = await confirmRef.current({
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
        notifyRef.current.success('已移除分析维度');
      } catch (err) {
        notifyRef.current.error('移除维度失败', err instanceof Error ? err.message : undefined);
      } finally {
        setRemovingDimId(null);
      }
    },
    [analysisId], // confirm excluded via confirmRef
  );

  // Group results by type for sectioned display (Req 3.1-3.5).
  const hasResults = results.length > 0;

  // The analysis workspace content (left column).
  const analysisContent = (
    <Space direction="vertical" size={SPACING.lg} style={{ width: '100%' }}>
      <Row gutter={[SPACING.lg, SPACING.lg]}>
        {/* File selection + upload */}
        <Col xs={24} lg={14}>
          <Card title="选择数据文件" variant="outlined">
            {filesLoading ? (
              <LoadingIndicator tip="正在加载文件列表…" size="default" />
            ) : files.length > 0 ? (
              <Select
                style={{ width: '100%' }}
                placeholder="请选择一个数据文件"
                value={selectedFileId ?? undefined}
                onChange={(value) => setSelectedFileId(value)}
                options={files.map((file) => ({
                  value: file.id,
                  label: fileOptionLabel(file),
                }))}
                showSearch
                optionFilterProp="label"
              />
            ) : (
              <Empty description="暂无数据文件，请先上传一个文件" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="上传新文件" variant="outlined">
            <FileUpload
              onUploaded={(file) => {
                notifyRef.current.info('文件已上传，正在刷新列表…');
                void loadFiles(file.id);
              }}
            />
          </Card>
        </Col>
      </Row>

      {selectedFile ? (
        <>
          {/* Data preview (Req 2.2) */}
          <Card title="数据预览（前 10 行）" variant="outlined">
            {fileDetailLoading ? (
              <LoadingIndicator tip="正在加载数据预览…" size="default" />
            ) : preview ? (
              <DataPreviewTable preview={preview} />
            ) : (
              <Empty description="无法加载数据预览" />
            )}
          </Card>

          {/* Data quality summary (Req 2.6) */}
          <Card title="数据质量摘要" variant="outlined">
            {fileDetailLoading ? (
              <LoadingIndicator tip="正在加载数据质量报告…" size="default" />
            ) : quality ? (
              <DataQualitySummary quality={quality} />
            ) : (
              <Empty description="无法加载数据质量报告" />
            )}
          </Card>

          {/* Start analysis + progress (Req 3.7) */}
          <Card title="AI 多维度分析" variant="outlined">
            <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
              <Space wrap>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={analyzing}
                  disabled={!selectedFileId || fileDetailLoading}
                  onClick={() => void handleStartAnalysis()}
                >
                  {hasResults ? '重新分析' : '开始分析'}
                </Button>
                {hasResults ? (
                  <Text type="secondary">分析已完成，可在下方查看结果与图表。</Text>
                ) : null}
              </Space>
              {analyzing ? <AnalysisProgress /> : null}
            </Space>
          </Card>

          {/* Analysis dimensions (Req 9.19-9.22) */}
          {hasResults ? (
            <Card title="分析维度" variant="outlined">
              <DimensionList
                dimensions={dimensions}
                onRemove={(dimension) => void handleRemoveDimension(dimension)}
                removingId={removingDimId}
              />
            </Card>
          ) : null}

          {/* Analysis results (Req 3.1-3.5) */}
          {hasResults ? (
            <Card title="分析结果" variant="outlined">
              {results.map((result) => (
                <ResultSection key={result.id} result={result} />
              ))}
            </Card>
          ) : null}

          {/* Charts (Req 4.1-4.6) */}
          {hasResults ? (
            <Card title="可视化图表" variant="outlined">
              <ChartGrid charts={charts} />
            </Card>
          ) : null}

          {/* Report generation + download (Req 5.5-5.7). Available once the
              analysis has produced results; the User can generate the report
              (reusing one the Agent already produced) and download it inline. */}
          {hasResults && analysisId ? (
            <Card title="分析报告" variant="outlined">
              <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
                {report ? (
                  <Text type="secondary">{`当前报告：${report.title}`}</Text>
                ) : (
                  <Text type="secondary">点击「生成报告」以生成结构化分析报告，并可下载为 PDF 或 Word 格式。</Text>
                )}
                <ReportDownloadControl
                  analysisId={analysisId}
                  report={report}
                  onReportGenerated={setReport}
                />
              </Space>
            </Card>
          ) : null}
        </>
      ) : null}
    </Space>
  );

  // Persistent chat panel (right column on desktop, stacked on tablet) (Req 9.1, 9.4).
  // Linked to the current analysis session once one has been started (Req 9.14).
  const chatPanel = (
    <ChatPanel
      analysisSessionId={analysisId ?? undefined}
      onArtifacts={handleChatArtifacts}
      height={isDesktop ? 'calc(100vh - 168px)' : 520}
    />
  );

  return (
    <PageContainer
      title="数据分析"
      description="选择已上传的数据文件或上传新文件，由 AI 进行多维度分析并生成可视化结果。"
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void loadFiles(selectedFileId ?? undefined)}
          disabled={filesLoading}
        >
          刷新文件
        </Button>
      }
    >
      {/* Two-column layout: analysis content alongside a persistent chat panel
          on desktop; stacked on tablet (Req 9.1, 9.4, 12.5). */}
      <Row gutter={[SPACING.lg, SPACING.lg]} wrap>
        <Col xs={24} xl={16}>
          {analysisContent}
        </Col>
        <Col xs={24} xl={8}>
          {isDesktop ? (
            <div style={{ position: 'sticky', top: SPACING.lg }}>{chatPanel}</div>
          ) : (
            chatPanel
          )}
        </Col>
      </Row>
    </PageContainer>
  );
}

export default AnalysisPage;
