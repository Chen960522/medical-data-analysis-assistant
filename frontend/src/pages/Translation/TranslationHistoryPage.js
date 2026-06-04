import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { HistoryList } from './components/HistoryList';
import { BilingualDocumentView } from './components/BilingualDocumentView';
import { DownloadControl } from './components/DownloadControl';
const { Text } = Typography;
export function TranslationHistoryPage() {
    const notify = useNotify();
    const confirm = useConfirm();
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    // Selected record + its loaded bilingual result (Req 11.45).
    const [selected, setSelected] = useState(null);
    const [result, setResult] = useState(null);
    const [resultLoading, setResultLoading] = useState(false);
    const loadHistory = useCallback(async () => {
        setLoading(true);
        try {
            const response = await translationService.getHistory();
            setRecords(response.records);
        }
        catch (err) {
            notify.error('加载翻译历史失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setLoading(false);
        }
    }, [notify]);
    useEffect(() => {
        void loadHistory();
    }, [loadHistory]);
    /** Open a past translation's bilingual view (Req 11.45). */
    const handleOpen = useCallback(async (item) => {
        setSelected(item);
        setResult(null);
        setResultLoading(true);
        try {
            const loaded = await translationService.getResult(item.id);
            setResult(loaded);
        }
        catch (err) {
            notify.error('加载翻译结果失败', err instanceof Error ? err.message : undefined);
            setSelected(null);
        }
        finally {
            setResultLoading(false);
        }
    }, [notify]);
    /** Delete a translation record after confirmation (Req 11.46). */
    const handleDelete = useCallback(async (item) => {
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
        setResult(null);
    }, []);
    return (_jsx(PageContainer, { title: "\u7FFB\u8BD1\u5386\u53F2", description: "\u7BA1\u7406\u5DF2\u5B8C\u6210\u7684 PDF \u6587\u732E\u7FFB\u8BD1\u8BB0\u5F55\uFF0C\u53EF\u67E5\u770B\u53CC\u8BED\u5BF9\u6BD4\u7ED3\u679C\u6216\u5220\u9664\u8BB0\u5F55\u3002", extra: !selected ? (_jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: () => void loadHistory(), loading: loading, children: "\u5237\u65B0" })) : undefined, children: selected ? (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsxs(Space, { size: SPACING.sm, wrap: true, align: "center", children: [_jsx(Button, { icon: _jsx(ArrowLeftOutlined, {}), onClick: handleBack, children: "\u8FD4\u56DE\u5217\u8868" }), _jsx(Text, { strong: true, children: selected.original_filename })] }), _jsx(Card, { variant: "outlined", extra: result ? _jsx(DownloadControl, { translationId: result.translation_id }) : null, children: resultLoading ? (_jsx(Text, { type: "secondary", children: "\u6B63\u5728\u52A0\u8F7D\u7FFB\u8BD1\u7ED3\u679C\u2026" })) : result ? (_jsx(BilingualDocumentView, { originalParagraphs: result.original_paragraphs, translatedParagraphs: result.translated_paragraphs, sourceLanguage: result.source_language, targetLanguage: result.target_language })) : (_jsx(Text, { type: "secondary", children: "\u6682\u65E0\u7FFB\u8BD1\u7ED3\u679C" })) })] })) : (_jsx(Card, { variant: "outlined", children: _jsx(HistoryList, { records: records, loading: loading, deletingId: deletingId, onOpen: handleOpen, onDelete: handleDelete }) })) }));
}
export default TranslationHistoryPage;
