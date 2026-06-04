import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
const { Text } = Typography;
export function LanguageControl({ value, onChange, disabled = false, detectedLanguage, targetLanguage, }) {
    return (_jsxs(Space, { direction: "vertical", size: SPACING.xs, style: { width: '100%' }, children: [_jsxs(Space, { size: SPACING.sm, wrap: true, children: [_jsx(Text, { strong: true, children: "\u6E90\u8BED\u8A00\uFF1A" }), _jsxs(Radio.Group, { value: value, onChange: (e) => onChange(e.target.value), disabled: disabled, buttonStyle: "solid", children: [_jsx(Radio.Button, { value: "auto", children: "\u81EA\u52A8\u68C0\u6D4B" }), _jsx(Radio.Button, { value: "zh", children: "\u4E2D\u6587" }), _jsx(Radio.Button, { value: "en", children: "\u82F1\u6587" })] })] }), detectedLanguage ? (_jsxs(Text, { type: "secondary", children: ["\u68C0\u6D4B\u5230\u7684\u6E90\u8BED\u8A00\uFF1A", languageLabel(detectedLanguage), targetLanguage
                        ? `，翻译方向：${languageLabel(detectedLanguage)} → ${languageLabel(targetLanguage)}`
                        : null] })) : (_jsx(Text, { type: "secondary", children: "\u53EF\u624B\u52A8\u6307\u5B9A\u6E90\u8BED\u8A00\uFF1B\u9009\u62E9\u300C\u81EA\u52A8\u68C0\u6D4B\u300D\u65F6\u7531\u7CFB\u7EDF\u8BC6\u522B\u6587\u6863\u4E3B\u8981\u8BED\u8A00\u3002" }))] }));
}
export default LanguageControl;
