/**
 * Design tokens for the Medical Data Analysis Assistant.
 *
 * These tokens define the visual language of the platform:
 * - A calming medical blue primary palette complemented by neutral grays (Req 12.2).
 * - Accent colors used sparingly for key actions, alerts and insights (Req 12.3).
 * - An 8px base-unit spacing grid (Req 12.11).
 * - A constrained typographic scale (max 3 heading sizes, 2 body sizes) (Req 12.10).
 *
 * All foreground/background color pairs are chosen to satisfy WCAG 2.1 AA
 * contrast ratios (>= 4.5:1 for normal text, >= 3:1 for large text) in both
 * the light and dark themes (Req 12.4, 12.29).
 */
/** Base spacing unit in pixels. All spacing values are multiples of this. */
export const SPACING_UNIT = 8;
/**
 * 8px-based spacing scale. Use `spacing(n)` to get `n * 8` pixels.
 * e.g. spacing(1) = 8, spacing(2) = 16, spacing(3) = 24.
 */
export const spacing = (multiplier) => SPACING_UNIT * multiplier;
/** Named spacing aliases for common use cases. */
export const SPACING = {
    xs: spacing(0.5), // 4
    sm: spacing(1), // 8
    md: spacing(2), // 16
    lg: spacing(3), // 24
    xl: spacing(4), // 32
    xxl: spacing(6), // 48
};
/**
 * Responsive layout breakpoints (Req 12.5).
 * - Desktop: >= 1280px
 * - Tablet: 768px - 1279px
 */
export const BREAKPOINTS = {
    tablet: 768,
    desktop: 1280,
};
/** Minimum touch target size for tablet viewports (Req 12.8). */
export const MIN_TOUCH_TARGET = 44;
/** Transition duration for navigation / state changes (Req 12.13, <= 300ms). */
export const TRANSITION_DURATION_MS = 250;
/** Auto-dismiss duration for success notifications (Req 12.16, within 3s). */
export const NOTIFICATION_DURATION_SEC = 3;
/**
 * Brand color palette. The primary is a medical blue tuned for AA contrast
 * against white backgrounds when used for large text and UI accents.
 */
export const PALETTE = {
    // Primary medical blue
    primary: '#1677ff',
    primaryHover: '#4096ff',
    primaryActive: '#0958d9',
    // Functional / accent colors (used sparingly)
    success: '#52c41a',
    warning: '#faad14',
    error: '#ff4d4f',
    info: '#1677ff',
    // Neutral grays
    neutral: {
        white: '#ffffff',
        gray1: '#f5f7fa',
        gray2: '#e8ecf1',
        gray3: '#d0d7de',
        gray4: '#8c98a4',
        gray5: '#5b6670',
        gray6: '#3a424a',
        gray7: '#262d33',
        gray8: '#1a1f24',
        black: '#0d1117',
    },
};
/**
 * Typographic scale (Req 12.10).
 * Headings: 3 sizes. Body: 2 sizes.
 */
export const TYPOGRAPHY = {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', " +
        "'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif",
    headingSizes: {
        h1: 28,
        h2: 22,
        h3: 18,
    },
    bodySizes: {
        base: 14,
        small: 12,
    },
    lineHeight: 1.5715,
};
/** Shared geometry tokens. */
export const GEOMETRY = {
    borderRadius: 6,
    borderRadiusLg: 8,
};
