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
import type { DownloadFormat, DownloadMode } from '../../../types/translation';

const { Text } = Typography;

export interface DownloadControlProps {
  translationId: string;
}

export function DownloadControl({ translationId }: DownloadControlProps) {
  const notify = useNotify();
  const [format, setFormat] = useState<DownloadFormat>('pdf');
  const [mode, setMode] = useState<DownloadMode>('bilingual');
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await translationService.getDownloadUrl(translationId, format, mode);
      // Open the presigned URL to trigger the browser download (Req 11.40).
      window.open(response.download_url, '_blank', 'noopener,noreferrer');
      notify.success('已开始下载翻译文档');
    } catch (err) {
      notify.error(
        '下载失败',
        err instanceof Error ? err.message : '该格式的翻译文档暂不可用，请稍后重试。',
      );
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Space size={SPACING.sm} wrap align="center">
      <Text strong>下载：</Text>
      <Select<DownloadFormat>
        value={format}
        onChange={setFormat}
        style={{ width: 120 }}
        aria-label="下载格式"
        options={[
          { label: 'PDF', value: 'pdf' },
          { label: 'Word', value: 'docx' },
        ]}
      />
      <Select<DownloadMode>
        value={mode}
        onChange={setMode}
        style={{ width: 140 }}
        aria-label="内容模式"
        options={[
          { label: '双语对照', value: 'bilingual' },
          { label: '仅翻译', value: 'translation' },
        ]}
      />
      <Button
        type="primary"
        icon={<DownloadOutlined />}
        loading={downloading}
        onClick={handleDownload}
      >
        下载
      </Button>
    </Space>
  );
}

export default DownloadControl;
