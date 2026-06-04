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
import type { UploadProps } from 'antd';

import { formatFileSize } from '../../../components/Upload/FileUpload';
import { useNotify } from '../../../hooks/useNotify';
import { translationService } from '../../../services/translationService';
import type { UploadProgress } from '../../../services/dataService';
import { SPACING } from '../../../theme/tokens';
import type { TranslationUploadResponse } from '../../../types/translation';

const { Dragger } = Upload;
const { Text } = Typography;

/** Accepted extension for PDF translation uploads (Req 11.2). */
const PDF_EXTENSION = '.pdf';
/** Maximum PDF size: 50MB (Req 11.3). */
const MAX_PDF_SIZE_MB = 50;

export interface PdfUploadProps {
  /** Called after a successful upload with the created translation record. */
  onUploaded?: (record: TranslationUploadResponse) => void;
}

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf('.');
  return idx === -1 ? '' : filename.slice(idx).toLowerCase();
}

export function PdfUpload({ onUploaded }: PdfUploadProps) {
  const notify = useNotify();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const maxBytes = MAX_PDF_SIZE_MB * 1024 * 1024;

  /** Validate a file before upload. Returns an error message or null (Req 11.5, 11.6). */
  const validate = (file: File): string | null => {
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

  const doUpload = async (file: File) => {
    setUploading(true);
    setProgress(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const record = await translationService.upload(
        file,
        (p: UploadProgress) => setProgress(p.percent),
        controller.signal,
      );
      notify.success(
        `PDF「${record.original_filename}」上传成功（${formatFileSize(record.file_size)}）`,
      );
      onUploaded?.(record);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        notify.warning('上传已取消');
      } else {
        notify.error(
          'PDF 上传失败',
          err instanceof Error ? err.message : '请检查网络连接后重试。',
        );
      }
    } finally {
      setUploading(false);
      setProgress(0);
      abortRef.current = null;
    }
  };

  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    const error = validate(file as File);
    if (error) {
      // Pre-validation failure feedback with recovery hint (Req 11.4, 11.5, 12.17).
      notify.error('无法上传该文件', error);
      return Upload.LIST_IGNORE;
    }
    void doUpload(file as File);
    return false; // Prevent antd's default upload; handled manually.
  };

  const cancelUpload = () => {
    abortRef.current?.abort();
  };

  return (
    <div>
      <Dragger
        multiple={false}
        showUploadList={false}
        beforeUpload={beforeUpload}
        disabled={uploading}
        accept={PDF_EXTENSION}
        aria-label="PDF 文献上传区域"
      >
        <p className="ant-upload-drag-icon">
          <FilePdfOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽 PDF 文献到此区域上传</p>
        <p className="ant-upload-hint">
          仅支持 PDF 格式，单个文件不超过 {MAX_PDF_SIZE_MB}MB
        </p>
      </Dragger>

      {uploading ? (
        <div style={{ marginTop: SPACING.md }} aria-live="polite">
          <Text type="secondary">正在上传…</Text>
          <Progress percent={progress} status="active" />
          <Button size="small" onClick={cancelUpload} style={{ marginTop: SPACING.xs }}>
            取消上传
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default PdfUpload;
