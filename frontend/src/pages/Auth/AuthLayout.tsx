/**
 * Centered authentication layout.
 *
 * Shared shell for the login and registration pages, presenting a branded,
 * centered card consistent with the platform's design system (Req 12.9).
 */

import { Card, Typography } from 'antd';
import type { ReactNode } from 'react';

import { SPACING } from '../../theme/tokens';

const { Title, Text } = Typography;

export interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: SPACING.lg,
        background: 'var(--ant-color-bg-layout, #f5f7fa)',
      }}
    >
      <Card style={{ width: '100%', maxWidth: 420 }} variant="outlined">
        <div style={{ textAlign: 'center', marginBottom: SPACING.lg }}>
          <Title level={2} style={{ marginBottom: SPACING.xs }}>
            {title}
          </Title>
          {subtitle ? <Text type="secondary">{subtitle}</Text> : null}
        </div>
        {children}
      </Card>
    </div>
  );
}

export default AuthLayout;
