import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Translation download control (Req 11.37-11.41).
 *
 * Lets the user choose the export format (PDF / Word) and content mode
 * (bilingual / translated-only) BEFORE downloading (Req 11.41), then resolves a
 * presigned download URL from `GET /translation/{id}/download` and triggers a
 * browser download/open. A missing export (backend 404) is surfaced gracefully
 * via `useNotify` (Req 12.17).
 */
import { useState } from 'react';
import { Button, Select, Space, Typography } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useNotify } from '../../../hooks/useNotify';
import { translationService } from '../../../services/translationService';
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
export function DownloadControl({ translationId }) {
    const notify = useNotify();
    const [format, setFormat] = useState('pdf');
    const [mode, setMode] = useState('bilingual');
    const [downloading, setDownloading] = useState(false);
    const handleDownload = async () => {
        setDownloading(true);
        try {
            const response = await translationService.getDownloadUrl(translationId, format, mode);
            // Open the presigned URL to trigger the browser download (Req 11.40).
            window.open(response.download_url, '_blank', 'noopener,noreferrer');
            notify.success('已开始下载翻译文档');
        }
        catch (err) {
            notify.error('下载失败', err instanceof Error ? err.message : '该格式的翻译文档暂不可用，请稍后重试。');
        }
        finally {
            setDownloading(false);
        }
    };
    return (_jsxs(Space, { size: SPACING.sm, wrap: true, align: "center", children: [_jsx(Text, { strong: true, children: "\u4E0B\u8F7D\uFF1A" }), _jsx(Select, { value: format, onChange: setFormat, style: { width: 120 }, "aria-label": "\u4E0B\u8F7D\u683C\u5F0F", options: [
                    { label: 'PDF', value: 'pdf' },
                    { label: 'Word', value: 'docx' },
                ] }), _jsx(Select, { value: mode, onChange: setMode, style: { width: 140 }, "aria-label": "\u5185\u5BB9\u6A21\u5F0F", options: [
                    { label: '双语对照', value: 'bilingual' },
                    { label: '仅翻译', value: 'translation' },
                ] }), _jsx(Button, { type: "primary", icon: _jsx(DownloadOutlined, {}), loading: downloading, onClick: handleDownload, children: "\u4E0B\u8F7D" })] }));
}
export default DownloadControl;
