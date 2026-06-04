import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Status tag.
 *
 * Renders a color-coded status indicator that also includes an icon and a text
 * label, so meaning is never conveyed by color alone (Req 12.34).
 */
import { Tag } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, SyncOutlined, } from '@ant-design/icons';
const STATUS_CONFIG = {
    success: { color: 'success', icon: _jsx(CheckCircleOutlined, {}) },
    error: { color: 'error', icon: _jsx(CloseCircleOutlined, {}) },
    processing: { color: 'processing', icon: _jsx(SyncOutlined, { spin: true }) },
    pending: { color: 'default', icon: _jsx(ClockCircleOutlined, {}) },
    warning: { color: 'warning', icon: _jsx(ClockCircleOutlined, {}) },
};
export function StatusTag({ kind, label }) {
    const config = STATUS_CONFIG[kind];
    return (_jsx(Tag, { color: config.color, icon: config.icon, children: label }));
}
export default StatusTag;
