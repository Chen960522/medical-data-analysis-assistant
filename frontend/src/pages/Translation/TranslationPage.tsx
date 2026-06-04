/**
 * PDF translation page.
 *
 * A dedicated PDF literature translation module, separate from the data upload
 * (Req 11.1). It walks the user through the full workflow:
 *
 * 1. Upload a PDF (PDF only, ≤ 50MB) with a progress bar (Req 11.1-11.8).
 * 2. Show an upload confirmation with file name, size, and page count when
 *    available (Req 11.7).
 * 3. Choose source language (auto-detect or manual override) and trigger
 *    full-document translation, showing a percentage progress bar while the
 *    synchronous translate call runs (Req 11.19, 11.21, 11.28).
 * 4. Display the detected source language + translation direction (Req 11.19).
 * 5. Render the bilingual comparison view with synchronized scrolling,
 *    paragraph click-to-highlight, and a view switch (Req 11.30-11.36).
 * 6. Download the result (PDF/Word, bilingual/translated-only) (Req 11.37-11.41).
 *
 * A link to the dedicated translation-history management page is provided
 * (Req 11.44).
 */

import { useCallback, useState } from 'react';
import { Alert, Button, Card, Descriptions, Space, Typography } from 'antd';
import { FileSyncOutlined, TranslationOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';

import { PageContainer, StatusTag } from '../../components/Common';
import { formatFileSize } from '../../components/Upload/FileUpload';
import { useNotify } from '../../hooks/useNotify';
import { ApiError } from '../../services/apiClient';
import { translationService } from '../../services/translationService';
import { SPACING } from '../../theme/tokens';
import type {
  SourceLanguageChoice,
  TranslationResultResponse,
  TranslationUploadResponse,
} from '../../types/translation';

import { PdfUpload } from './components/PdfUpload';
import { LanguageControl } from './components/LanguageControl';
import { TranslationProgress } from './components/TranslationProgress';
import { BilingualDocumentView } from './components/BilingualDocumentView';
import { DownloadControl } from './components/DownloadControl';

const { Text } = Typography;

export function TranslationPage() {
  const notify = useNotify();

  const [record, setRecord] = useState<TranslationUploadResponse | null>(null);
  const [sourceChoice, setSourceChoice] = useState<SourceLanguageChoice>('auto');
  const [translating, setTranslating] = useState(false);
  const [progressPercent, setProgressPercent] = useState<number | null>(null);
  const [result, setResult] = useState<TranslationResultResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Reset workflow state when a new PDF is uploaded (Req 11.7). */
  const handleUploaded = useCallback((uploaded: TranslationUploadResponse) => {
    setRecord(uploaded);
    setResult(null);
    setError(null);
    setSourceChoice('auto');
    setProgressPercent(null);
  }, []);

  /** Trigger full-document translation (Req 11.21). */
  const handleTranslate = useCallback(async () => {
    if (!record) {
      return;
    }
    setTranslating(true);
    setError(null);
    setProgressPercent(null);

    // Poll status for a concrete progress percentage while the synchronous
    // translate call runs (Req 11.28). Polling is best-effort.
    const poll = window.setInterval(async () => {
      try {
        const status = await translationService.getStatus(record.id);
        if (typeof status.progress === 'number') {
          setProgressPercent(status.progress);
        }
      } catch {
        // Ignore polling errors; the translate call result is authoritative.
      }
    }, 2000);

    try {
      const body =
        sourceChoice === 'auto' ? undefined : { source_language: sourceChoice };
      const translated = await translationService.translate(record.id, body);
      setResult(translated);
      setProgressPercent(100);
      notify.success('翻译完成');
    } catch (err) {
      const message =
        err instanceof ApiError || err instanceof Error
          ? err.message
          : '翻译失败，请稍后重试。';
      setError(message);
      notify.error('翻译失败', message);
    } finally {
      window.clearInterval(poll);
      setTranslating(false);
    }
  }, [record, sourceChoice, notify]);

  const detectedSource = result?.source_language ?? null;
  const detectedTarget = result?.target_language ?? null;

  return (
    <PageContainer
      title="PDF 翻译"
      description="上传 PDF 医学文献并进行中英文全文翻译，支持双语对比查看与结果下载。"
      extra={
        <Link to="/translation-history">
          <Button icon={<FileSyncOutlined />}>翻译历史</Button>
        </Link>
      }
    >
      <Space direction="vertical" size={SPACING.lg} style={{ width: '100%' }}>
        {/* Step 1: upload (Req 11.1-11.8). */}
        <Card title="上传 PDF 文献" variant="outlined">
          <PdfUpload onUploaded={handleUploaded} />
        </Card>

        {/* Step 2: upload confirmation + translate trigger (Req 11.7, 11.19, 11.21). */}
        {record ? (
          <Card title="文件信息" variant="outlined">
            <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
              <Descriptions
                column={{ xs: 1, sm: 2, md: 3 }}
                size="small"
                items={[
                  { key: 'name', label: '文件名', children: record.original_filename },
                  {
                    key: 'size',
                    label: '文件大小',
                    children: formatFileSize(record.file_size),
                  },
                  {
                    key: 'pages',
                    label: '页数',
                    children:
                      record.page_count != null ? `${record.page_count} 页` : '解析后显示',
                  },
                ]}
              />

              <LanguageControl
                value={sourceChoice}
                onChange={setSourceChoice}
                disabled={translating}
                detectedLanguage={detectedSource}
                targetLanguage={detectedTarget}
              />

              <Space size={SPACING.sm} wrap>
                <Button
                  type="primary"
                  icon={<TranslationOutlined />}
                  loading={translating}
                  onClick={handleTranslate}
                >
                  {result ? '重新翻译' : '翻译'}
                </Button>
                {result ? <StatusTag kind="success" label="翻译完成" /> : null}
              </Space>

              {translating ? <TranslationProgress percent={progressPercent} /> : null}

              {error ? (
                <Alert
                  type="error"
                  showIcon
                  message="翻译失败"
                  description={`${error} 请稍后重试或更换文档。`}
                />
              ) : null}
            </Space>
          </Card>
        ) : null}

        {/* Step 3: bilingual view + download (Req 11.30-11.41). */}
        {result ? (
          <Card
            title="翻译结果"
            variant="outlined"
            extra={<DownloadControl translationId={result.translation_id} />}
          >
            <BilingualDocumentView
              originalParagraphs={result.original_paragraphs}
              translatedParagraphs={result.translated_paragraphs}
              sourceLanguage={result.source_language}
              targetLanguage={result.target_language}
            />
          </Card>
        ) : record && !translating ? (
          <Text type="secondary">点击「翻译」开始全文翻译，完成后将在此显示双语对比结果。</Text>
        ) : null}
      </Space>
    </PageContainer>
  );
}

export default TranslationPage;
