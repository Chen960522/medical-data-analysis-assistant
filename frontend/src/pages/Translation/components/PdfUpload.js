import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Dedicated PDF upload component for the translation module.
 *
 * Separate from the data-analysis upload (Req 11.1): it posts to the
 * `/translation/upload` endpoint and accepts ONLY `.pdf` files (Req 11.2/11.5)
 * up to 50MB (Req 11.3/11.6). Supports drag-and-drop and the file-selection
 * dialog (Req 11.8), performs client-side format/size pre-validation
 * (Req 11.4), and displays an upload progress bar (Req 12.14) with
 * success/failure feedback (Req 11.7).
 *
 * Modeled on `components/Upload/FileUpload.tsx` for UX but wired to
 * `translationService.upload` since the PDF translation upload uses a different
 * endpoint and response shape.
 */
import { useRef, useState } from 'react';
import { Button, Progress, Typography, Upload } from 'antd';
import { FilePdfOutlined } from '@ant-design/icons';
import { formatFileSize } from '../../../components/Upload/FileUpload';
import { useNotify } from '../../../hooks/useNotify';
import { translationService } from '../../../services/translationService';
import { SPACING } from '../../../theme/tokens';
const { Dragger } = Upload;
const { Text } = Typography;
/** Accepted extension for PDF translation uploads (Req 11.2). */
const PDF_EXTENSION = '.pdf';
/** Maximum PDF size: 50MB (Req 11.3). */
const MAX_PDF_SIZE_MB = 50;
function getExtension(filename) {
    const idx = filename.lastIndexOf('.');
    return idx === -1 ? '' : filename.slice(idx).toLowerCase();
}
export function PdfUpload({ onUploaded }) {
    const notify = useNotify();
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const abortRef = useRef(null);
    const maxBytes = MAX_PDF_SIZE_MB * 1024 * 1024;
    /** Validate a file before upload. Returns an error message or null (Req 11.5, 11.6). */
    const validate = (file) => {
        if (getExtension(file.name) !== PDF_EXTENSION) {
            return '仅支持 PDF 格式文件（.pdf）。';
        }
        if (file.size === 0) {
            return '文件为空，请选择有效的 PDF 文件。';
        }
        if (file.size > maxBytes) {
            return `文件大小超过上限（最大 ${MAX_PDF_SIZE_MB}MB）。`;
        }
        return null;
    };
    const doUpload = async (file) => {
        setUploading(true);
        setProgress(0);
        const controller = new AbortController();
        abortRef.current = controller;
        try {
            const record = await translationService.upload(file, (p) => setProgress(p.percent), controller.signal);
            notify.success(`PDF「${record.original_filename}」上传成功（${formatFileSize(record.file_size)}）`);
            onUploaded?.(record);
        }
        catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') {
                notify.warning('上传已取消');
            }
            else {
                notify.error('PDF 上传失败', err instanceof Error ? err.message : '请检查网络连接后重试。');
            }
        }
        finally {
            setUploading(false);
            setProgress(0);
            abortRef.current = null;
        }
    };
    const beforeUpload = (file) => {
        const error = validate(file);
        if (error) {
            // Pre-validation failure feedback with recovery hint (Req 11.4, 11.5, 12.17).
            notify.error('无法上传该文件', error);
            return Upload.LIST_IGNORE;
        }
        void doUpload(file);
        return false; // Prevent antd's default upload; handled manually.
    };
    const cancelUpload = () => {
        abortRef.current?.abort();
    };
    return (_jsxs("div", { children: [_jsxs(Dragger, { multiple: false, showUploadList: false, beforeUpload: beforeUpload, disabled: uploading, accept: PDF_EXTENSION, "aria-label": "PDF \u6587\u732E\u4E0A\u4F20\u533A\u57DF", children: [_jsx("p", { className: "ant-upload-drag-icon", children: _jsx(FilePdfOutlined, {}) }), _jsx("p", { className: "ant-upload-text", children: "\u70B9\u51FB\u6216\u62D6\u62FD PDF \u6587\u732E\u5230\u6B64\u533A\u57DF\u4E0A\u4F20" }), _jsxs("p", { className: "ant-upload-hint", children: ["\u4EC5\u652F\u6301 PDF \u683C\u5F0F\uFF0C\u5355\u4E2A\u6587\u4EF6\u4E0D\u8D85\u8FC7 ", MAX_PDF_SIZE_MB, "MB"] })] }), uploading ? (_jsxs("div", { style: { marginTop: SPACING.md }, "aria-live": "polite", children: [_jsx(Text, { type: "secondary", children: "\u6B63\u5728\u4E0A\u4F20\u2026" }), _jsx(Progress, { percent: progress, status: "active" }), _jsx(Button, { size: "small", onClick: cancelUpload, style: { marginTop: SPACING.xs }, children: "\u53D6\u6D88\u4E0A\u4F20" })] })) : null] }));
}
export default PdfUpload;
