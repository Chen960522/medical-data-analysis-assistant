/**
 * Translation history management page (Req 11.43-11.47, 11.50).
 *
 * Lists all of the authenticated user's translation records, newest first
 * (Req 11.44), showing file name, size, page count, translation direction,
 * status, and dates. Selecting a completed record fetches its
 * Translation_Result and displays the bilingual comparison view (Req 11.45);
 * deleting a record prompts a confirmation dialog before permanently removing
 * it (Req 11.46).
 */

import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Space, Typography } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';

import { PageContainer } from '../../components/Common';
import { useConfirm } from '../../hooks/useConfirm';
import { useNotify } from '../../hooks/useNotify';
import { translationService } from '../../services/translationService';
import { SPACING } from '../../theme/tokens';
import type {
  TranslationHistoryItem,
  TranslationResultResponse,
} from '../../types/translation';

import { HistoryList } from './components/HistoryList';
import { BilingualDocumentView } from './components/BilingualDocumentView';
import { DownloadControl } from './components/DownloadControl';

const { Text } = Typography;

export function TranslationHistoryPage() {
  const notify = useNotify();
  const confirm = useConfirm();

  const [records, setRecords] = useState<TranslationHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Selected record + its loaded bilingual result (Req 11.45).
  const [selected, setSelected] = useState<TranslationHistoryItem | null>(null);
  const [result, setResult] = useState<TranslationResultResponse | null>(null);
  const [resultLoading, setResultLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const response = await translationService.getHistory();
      setRecords(response.records);
    } catch (err) {
      notify.error('加载翻译历史失败', err instanceof Error ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  /** Open a past translation's bilingual view (Req 11.45). */
  const handleOpen = useCallback(
    async (item: TranslationHistoryItem) => {
      setSelected(item);
      setResult(null);
      setResultLoading(true);
      try {
        const loaded = await translationService.getResult(item.id);
        setResult(loaded);
      } catch (err) {
        notify.error('加载翻译结果失败', err instanceof Error ? err.message : undefined);
        setSelected(null);
      } finally {
        setResultLoading(false);
      }
    },
    [notify],
  );

  /** Delete a translation record after confirmation (Req 11.46). */
  const handleDelete = useCallback(
    async (item: TranslationHistoryItem) => {
      const confirmed = await confirm({
        title: '删除翻译记录',
        content: `确定要删除「${item.original_filename}」的翻译记录吗？该操作不可恢复。`,
        danger: true,
      });
      if (!confirmed) {
        return;
      }
      setDeletingId(item.id);
      try {
        await translationService.deleteRecord(item.id);
        notify.success('翻译记录已删除');
        setRecords((prev) => prev.filter((r) => r.id !== item.id));
        if (selected?.id === item.id) {
          setSelected(null);
          setResult(null);
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
    setResult(null);
  }, []);

  return (
    <PageContainer
      title="翻译历史"
      description="管理已完成的 PDF 文献翻译记录，可查看双语对比结果或删除记录。"
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
            <Text strong>{selected.original_filename}</Text>
          </Space>
          <Card
            variant="outlined"
            extra={result ? <DownloadControl translationId={result.translation_id} /> : null}
          >
            {resultLoading ? (
              <Text type="secondary">正在加载翻译结果…</Text>
            ) : result ? (
              <BilingualDocumentView
                originalParagraphs={result.original_paragraphs}
                translatedParagraphs={result.translated_paragraphs}
                sourceLanguage={result.source_language}
                targetLanguage={result.target_language}
              />
            ) : (
              <Text type="secondary">暂无翻译结果</Text>
            )}
          </Card>
        </Space>
      ) : (
        <Card variant="outlined">
          <HistoryList
            records={records}
            loading={loading}
            deletingId={deletingId}
            onOpen={handleOpen}
            onDelete={handleDelete}
          />
        </Card>
      )}
    </PageContainer>
  );
}

export default TranslationHistoryPage;
