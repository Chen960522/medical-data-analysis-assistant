/**
 * Notification helper hook.
 *
 * Wraps Ant Design's App-level message/notification APIs to provide:
 * - Brief success notifications that auto-dismiss within 3 seconds (Req 12.16).
 * - User-friendly error messages with optional recovery suggestions (Req 12.17).
 *
 * Must be used within an <AntApp> context (provided by the root App component).
 */

import { App } from 'antd';

import { NOTIFICATION_DURATION_SEC } from '../theme/tokens';

export interface Notifier {
  success: (content: string) => void;
  error: (content: string, recovery?: string) => void;
  warning: (content: string) => void;
  info: (content: string) => void;
}

export const useNotify = (): Notifier => {
  const { message, notification } = App.useApp();

  return {
    success: (content) => {
      void message.success({ content, duration: NOTIFICATION_DURATION_SEC });
    },
    error: (content, recovery) => {
      notification.error({
        message: content,
        description: recovery,
        duration: 0, // Errors persist until dismissed so users can read recovery steps.
      });
    },
    warning: (content) => {
      void message.warning({ content, duration: NOTIFICATION_DURATION_SEC });
    },
    info: (content) => {
      void message.info({ content, duration: NOTIFICATION_DURATION_SEC });
    },
  };
};
