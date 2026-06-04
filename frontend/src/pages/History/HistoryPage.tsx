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
import type {
  AnalysisResult,
  AnalysisSession,
  Chart,
  Report,
} from '../../types/analysis';

import { AnalysisHistoryList } from './components/AnalysisHistoryList';
import { ResultSection } from '../Analysis/components/ResultSection';

const { Text } = Typography;

export function HistoryPage() {
  const notify = useNotify();
  const confirm = useConfirm();

  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Selected session + its loaded results/charts/report (Req 6.3).
  const [selected, setSelected] = useState<AnalysisSession | null>(null);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  /** Load the analysis history, newest first (Req 6.1, 6.2). */
  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const response = await analysisService.history();
      setSessions(response.sessions);
    } catch (err) {
      notify.error('加载分析历史失败', err instanceof Error ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  /** Open a historical analysis and load its full results, charts, report (Req 6.3). */
  const handleOpen = useCallback(
    async (session: AnalysisSession) => {
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
      } catch (err) {
        notify.error('加载分析详情失败', err instanceof Error ? err.message : undefined);
        setSelected(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [notify],
  );

  /** Delete an analysis record after confirmation (Req 6.4). */
  const handleDelete = useCallback(
    async (session: AnalysisSession) => {
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
      } catch (err) {
        notify.error('删除失败', err instanceof Error ? err.message : undefined);
      } finally {
        setDeletingId(null);
      }
    },
    [confirm, notify, selected],
  );

  const handleBack = useCallback(() => {
    setSelected(null);
    setResults([]);
    setCharts([]);
    setReport(null);
  }, []);

  const hasResults = results.length > 0;

  return (
    <PageContainer
      title="分析历史"
      description="查看并管理历史分析记录，可按日期降序浏览、查看完整分析结果与图表，或删除不再需要的记录。"
      extra={
        !selected ? (
          <Button icon={<ReloadOutlined />} onClick={() => void loadHistory()} loading={loading}>
            刷新
          </Button>
        ) : undefined
      }
    >
      {selected ? (
        <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
          <Space size={SPACING.sm} wrap align="center">
            <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
              返回列表
            </Button>
            <Text strong>分析编号：</Text>
            <Text code>{selected.id.slice(0, 8)}</Text>
          </Space>

          {detailLoading ? (
            <LoadingIndicator tip="正在加载分析详情…" />
          ) : (
            <>
              {/* Analysis results (Req 6.3, 3.1-3.5) */}
              <Card title="分析结果" variant="outlined">
                {hasResults ? (
                  results.map((result) => <ResultSection key={result.id} result={result} />)
                ) : (
                  <Empty description="暂无分析结果" />
                )}
              </Card>

              {/* Charts (Req 6.3, 4.1-4.6) */}
              <Card title="可视化图表" variant="outlined">
                {charts.length > 0 ? (
                  <ChartGrid charts={charts} />
                ) : (
                  <Empty description="暂无可视化图表" />
                )}
              </Card>

              {/* Report summary, if one was generated (Req 6.3). Download is task 13.2. */}
              {report ? (
                <Alert
                  type="info"
                  showIcon
                  message={`已生成分析报告：${report.title}`}
                  description="可在报告下载入口中导出完整报告（PDF/Word）。"
                />
              ) : null}
            </>
          )}
        </Space>
      ) : (
        <Card variant="outlined">
          <AnalysisHistoryList
            sessions={sessions}
            loading={loading}
            deletingId={deletingId}
            onOpen={(session) => void handleOpen(session)}
            onDelete={(session) => void handleDelete(session)}
          />
        </Card>
      )}
    </PageContainer>
  );
}

export default HistoryPage;
