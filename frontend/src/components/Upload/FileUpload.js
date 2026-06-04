import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Data file upload component.
 *
 * Supports drag-and-drop and file-dialog selection (Req 1.1, 11.8), performs
 * client-side format and size pre-validation (Req 1.4, 1.5, 11.5, 11.6),
 * displays an upload progress bar (Req 12.14), and surfaces success/failure
 * feedback confirming the file name and size (Req 1.6, 11.7).
 *
 * Defaults target the data-analysis upload (CSV/Excel/JSON up to 100MB) but the
 * accepted formats and size cap are configurable so the same component can be
 * reused for the PDF translation flow (PDF up to 50MB).
 */
import { useRef, useState } from 'react';
import { Button, Progress, Typography, Upload } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { dataService } from '../../services/dataService';
import { useNotify } from '../../hooks/useNotify';
import { SPACING } from '../../theme/tokens';
const { Dragger } = Upload;
const { Text } = Typography;
/** Default accepted formats for data analysis uploads (Req 1.1). */
export const DEFAULT_DATA_EXTENSIONS = ['.csv', '.xlsx', '.xls', '.json'];
/** Default max size for data files: 100MB (Req 1.3). */
export const DEFAULT_MAX_SIZE_MB = 100;
/** Format a byte count into a human-readable size string. */
export function formatFileSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    const kb = bytes / 1024;
    if (kb < 1024) {
        return `${kb.toFixed(1)} KB`;
    }
    return `${(kb / 1024).toFixed(2)} MB`;
}
function getExtension(filename) {
    const idx = filename.lastIndexOf('.');
    return idx === -1 ? '' : filename.slice(idx).toLowerCase();
}
export function FileUpload({ acceptExtensions = DEFAULT_DATA_EXTENSIONS, maxSizeMb = DEFAULT_MAX_SIZE_MB, onUploaded, hint, }) {
    const notify = useNotify();
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const abortRef = useRef(null);
    const maxBytes = maxSizeMb * 1024 * 1024;
    /** Validate a file before upload. Returns an error message or null. */
    const validate = (file) => {
        const ext = getExtension(file.name);
        if (!acceptExtensions.includes(ext)) {
            return `不支持的文件格式。支持的格式：${acceptExtensions.join('、')}`;
        }
        if (file.size === 0) {
            return '文件为空，请选择有效的文件。';
        }
        if (file.size > maxBytes) {
            return `文件大小超过上限（最大 ${maxSizeMb}MB）。`;
        }
        return null;
    };
    const doUpload = async (file) => {
        setUploading(true);
        setProgress(0);
        const controller = new AbortController();
        abortRef.current = controller;
        try {
            const response = await dataService.upload(file, (p) => setProgress(p.percent), controller.signal);
            notify.success(`文件「${response.file.original_filename}」上传成功（${formatFileSize(response.file.file_size)}）`);
            onUploaded?.(response.file);
        }
        catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') {
                notify.warning('上传已取消');
            }
            else {
                notify.error('文件上传失败', err instanceof Error ? err.message : '请检查网络连接后重试。');
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
            // Pre-validation failure feedback with recovery hint (Req 1.4, 1.5, 12.17).
            notify.error('无法上传该文件', error);
            return Upload.LIST_IGNORE;
        }
        void doUpload(file);
        return false; // Prevent antd's default upload; we handle it manually.
    };
    const cancelUpload = () => {
        abortRef.current?.abort();
    };
    return (_jsxs("div", { children: [_jsxs(Dragger, { multiple: false, showUploadList: false, beforeUpload: beforeUpload, disabled: uploading, accept: acceptExtensions.join(','), "aria-label": "\u6587\u4EF6\u4E0A\u4F20\u533A\u57DF", children: [_jsx("p", { className: "ant-upload-drag-icon", children: _jsx(InboxOutlined, {}) }), _jsx("p", { className: "ant-upload-text", children: "\u70B9\u51FB\u6216\u62D6\u62FD\u6587\u4EF6\u5230\u6B64\u533A\u57DF\u4E0A\u4F20" }), _jsx("p", { className: "ant-upload-hint", children: hint ??
                            `支持 ${acceptExtensions.join('、')} 格式，单个文件不超过 ${maxSizeMb}MB` })] }), uploading ? (_jsxs("div", { style: { marginTop: SPACING.md }, "aria-live": "polite", children: [_jsx(Text, { type: "secondary", children: "\u6B63\u5728\u4E0A\u4F20\u2026" }), _jsx(Progress, { percent: progress, status: "active" }), _jsx(Button, { size: "small", onClick: cancelUpload, style: { marginTop: SPACING.xs }, children: "\u53D6\u6D88\u4E0A\u4F20" })] })) : null] }));
}
export default FileUpload;
