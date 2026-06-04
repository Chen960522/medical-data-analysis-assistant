/**
 * Page content container.
 *
 * Provides consistent page padding and an optional title/description header
 * using the shared 8px spacing grid (Req 12.11) and constrained typography
 * (Req 12.10). Children are rendered within a max-width column that adapts to
 * tablet and desktop viewports (Req 12.5).
 */

import { Typography } from 'antd';
import type { CSSProperties, ReactNode } from 'react';

import { SPACING } from '../../theme/tokens';

const { Title, Paragraph } = Typography;

export interface PageContainerProps {
  title?: ReactNode;
  description?: ReactNode;
  /** Optional actions rendered on the right side of the header. */
  extra?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
}

export function PageContainer({ title, description, extra, children, style }: PageContainerProps) {
  return (
    <div style={{ padding: SPACING.lg, ...style }}>
      {(title || extra) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: SPACING.md,
            marginBottom: SPACING.md,
            flexWrap: 'wrap',
          }}
        >
          <div>
            {title ? (
              <Title level={2} style={{ marginBottom: description ? SPACING.xs : 0 }}>
                {title}
              </Title>
            ) : null}
            {description ? (
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {description}
              </Paragraph>
            ) : null}
          </div>
          {extra ? <div>{extra}</div> : null}
        </div>
      )}
      {children}
    </div>
  );
}

export default PageContainer;
