import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { PdfUpload } from './components/PdfUpload';
import { LanguageControl } from './components/LanguageControl';
import { TranslationProgress } from './components/TranslationProgress';
import { BilingualDocumentView } from './components/BilingualDocumentView';
import { DownloadControl } from './components/DownloadControl';
const { Text } = Typography;
export function TranslationPage() {
    const notify = useNotify();
    const [record, setRecord] = useState(null);
    const [sourceChoice, setSourceChoice] = useState('auto');
    const [translating, setTranslating] = useState(false);
    const [progressPercent, setProgressPercent] = useState(null);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    /** Reset workflow state when a new PDF is uploaded (Req 11.7). */
    const handleUploaded = useCallback((uploaded) => {
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
            }
            catch {
                // Ignore polling errors; the translate call result is authoritative.
            }
        }, 2000);
        try {
            const body = sourceChoice === 'auto' ? undefined : { source_language: sourceChoice };
            const translated = await translationService.translate(record.id, body);
            setResult(translated);
            setProgressPercent(100);
            notify.success('翻译完成');
        }
        catch (err) {
            const message = err instanceof ApiError || err instanceof Error
                ? err.message
                : '翻译失败，请稍后重试。';
            setError(message);
            notify.error('翻译失败', message);
        }
        finally {
            window.clearInterval(poll);
            setTranslating(false);
        }
    }, [record, sourceChoice, notify]);
    const detectedSource = result?.source_language ?? null;
    const detectedTarget = result?.target_language ?? null;
    return (_jsx(PageContainer, { title: "PDF \u7FFB\u8BD1", description: "\u4E0A\u4F20 PDF \u533B\u5B66\u6587\u732E\u5E76\u8FDB\u884C\u4E2D\u82F1\u6587\u5168\u6587\u7FFB\u8BD1\uFF0C\u652F\u6301\u53CC\u8BED\u5BF9\u6BD4\u67E5\u770B\u4E0E\u7ED3\u679C\u4E0B\u8F7D\u3002", extra: _jsx(Link, { to: "/translation-history", children: _jsx(Button, { icon: _jsx(FileSyncOutlined, {}), children: "\u7FFB\u8BD1\u5386\u53F2" }) }), children: _jsxs(Space, { direction: "vertical", size: SPACING.lg, style: { width: '100%' }, children: [_jsx(Card, { title: "\u4E0A\u4F20 PDF \u6587\u732E", variant: "outlined", children: _jsx(PdfUpload, { onUploaded: handleUploaded }) }), record ? (_jsx(Card, { title: "\u6587\u4EF6\u4FE1\u606F", variant: "outlined", children: _jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsx(Descriptions, { column: { xs: 1, sm: 2, md: 3 }, size: "small", items: [
                                    { key: 'name', label: '文件名', children: record.original_filename },
                                    {
                                        key: 'size',
                                        label: '文件大小',
                                        children: formatFileSize(record.file_size),
                                    },
                                    {
                                        key: 'pages',
                                        label: '页数',
                                        children: record.page_count != null ? `${record.page_count} 页` : '解析后显示',
                                    },
                                ] }), _jsx(LanguageControl, { value: sourceChoice, onChange: setSourceChoice, disabled: translating, detectedLanguage: detectedSource, targetLanguage: detectedTarget }), _jsxs(Space, { size: SPACING.sm, wrap: true, children: [_jsx(Button, { type: "primary", icon: _jsx(TranslationOutlined, {}), loading: translating, onClick: handleTranslate, children: result ? '重新翻译' : '翻译' }), result ? _jsx(StatusTag, { kind: "success", label: "\u7FFB\u8BD1\u5B8C\u6210" }) : null] }), translating ? _jsx(TranslationProgress, { percent: progressPercent }) : null, error ? (_jsx(Alert, { type: "error", showIcon: true, message: "\u7FFB\u8BD1\u5931\u8D25", description: `${error} 请稍后重试或更换文档。` })) : null] }) })) : null, result ? (_jsx(Card, { title: "\u7FFB\u8BD1\u7ED3\u679C", variant: "outlined", extra: _jsx(DownloadControl, { translationId: result.translation_id }), children: _jsx(BilingualDocumentView, { originalParagraphs: result.original_paragraphs, translatedParagraphs: result.translated_paragraphs, sourceLanguage: result.source_language, targetLanguage: result.target_language }) })) : record && !translating ? (_jsx(Text, { type: "secondary", children: "\u70B9\u51FB\u300C\u7FFB\u8BD1\u300D\u5F00\u59CB\u5168\u6587\u7FFB\u8BD1\uFF0C\u5B8C\u6210\u540E\u5C06\u5728\u6B64\u663E\u793A\u53CC\u8BED\u5BF9\u6BD4\u7ED3\u679C\u3002" })) : null] }) }));
}
export default TranslationPage;
