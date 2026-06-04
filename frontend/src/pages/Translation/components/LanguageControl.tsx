/**
 * Language detection display + manual override control (Req 11.16-11.20).
 *
 * Before translation runs, the user can let the Agent auto-detect the document
 * language or manually override the source language to 中文 / 英文 (Req 11.19).
 * After translation completes, the detected source language and the resulting
 * translation direction are shown (Req 11.19, 11.33).
 */

import { Radio, Space, Typography } from 'antd';

import { SPACING } from '../../../theme/tokens';
import { languageLabel } from '../../../types/translation';
import type { LanguageCode, SourceLanguageChoice } from '../../../types/translation';

const { Text } = Typography;

export interface LanguageControlProps {
  /** Current source-language selection ('auto' = let the Agent detect). */
  value: SourceLanguageChoice;
  onChange: (value: SourceLanguageChoice) => void;
  /** Disable the control while a translation is in progress. */
  disabled?: boolean;
  /** Detected source language after translation, when available (Req 11.19). */
  detectedLanguage?: LanguageCode | null;
  /** Target language after translation, when available (Req 11.33). */
  targetLanguage?: LanguageCode | null;
}

export function LanguageControl({
  value,
  onChange,
  disabled = false,
  detectedLanguage,
  targetLanguage,
}: LanguageControlProps) {
  return (
    <Space direction="vertical" size={SPACING.xs} style={{ width: '100%' }}>
      <Space size={SPACING.sm} wrap>
        <Text strong>源语言：</Text>
        <Radio.Group
          value={value}
          onChange={(e) => onChange(e.target.value as SourceLanguageChoice)}
          disabled={disabled}
          buttonStyle="solid"
        >
          <Radio.Button value="auto">自动检测</Radio.Button>
          <Radio.Button value="zh">中文</Radio.Button>
          <Radio.Button value="en">英文</Radio.Button>
        </Radio.Group>
      </Space>

      {detectedLanguage ? (
        <Text type="secondary">
          检测到的源语言：{languageLabel(detectedLanguage)}
          {targetLanguage
            ? `，翻译方向：${languageLabel(detectedLanguage)} → ${languageLabel(targetLanguage)}`
            : null}
        </Text>
      ) : (
        <Text type="secondary">
          可手动指定源语言；选择「自动检测」时由系统识别文档主要语言。
        </Text>
      )}
    </Space>
  );
}

export default LanguageControl;
