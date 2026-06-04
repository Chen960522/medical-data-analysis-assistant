/**
 * Confirmation dialog helper hook.
 *
 * Provides a promise-based confirmation dialog used before destructive actions
 * such as deleting an analysis record, removing a literature collection, or
 * deleting translation history (Req 12.15).
 *
 * Must be used within an <AntApp> context.
 */
import { App } from 'antd';
import { ExclamationCircleFilled } from '@ant-design/icons';
import { createElement } from 'react';
export const useConfirm = () => {
    const { modal } = App.useApp();
    return ({ title, content, okText = '确认', cancelText = '取消', danger = true }) => new Promise((resolve) => {
        modal.confirm({
            title,
            content,
            icon: createElement(ExclamationCircleFilled),
            okText,
            okButtonProps: { danger },
            cancelText,
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
        });
    });
};
