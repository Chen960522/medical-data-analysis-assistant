/**
 * Ant Design 5 theme configuration for light and dark modes.
 *
 * Builds {@link ThemeConfig} objects from the shared design tokens so that the
 * entire component library (buttons, forms, modals, tables, navigation) shares
 * a consistent visual language (Req 12.9). Both themes maintain adequate
 * contrast and readability (Req 12.29).
 */
import { theme as antdTheme } from 'antd';
import { GEOMETRY, PALETTE, TRANSITION_DURATION_MS, TYPOGRAPHY } from './tokens';
/** Shared token overrides applied to both light and dark themes. */
const sharedToken = {
    colorPrimary: PALETTE.primary,
    colorSuccess: PALETTE.success,
    colorWarning: PALETTE.warning,
    colorError: PALETTE.error,
    colorInfo: PALETTE.info,
    borderRadius: GEOMETRY.borderRadius,
    borderRadiusLG: GEOMETRY.borderRadiusLg,
    fontFamily: TYPOGRAPHY.fontFamily,
    fontSize: TYPOGRAPHY.bodySizes.base,
    fontSizeSM: TYPOGRAPHY.bodySizes.small,
    fontSizeHeading1: TYPOGRAPHY.headingSizes.h1,
    fontSizeHeading2: TYPOGRAPHY.headingSizes.h2,
    fontSizeHeading3: TYPOGRAPHY.headingSizes.h3,
    lineHeight: TYPOGRAPHY.lineHeight,
    motionDurationMid: `${TRANSITION_DURATION_MS}ms`,
    // Control height of 40px keeps interactive targets close to the 44px
    // minimum touch target recommended for tablet viewports (Req 12.8).
    controlHeight: 40,
};
export const lightTheme = {
    algorithm: antdTheme.defaultAlgorithm,
    token: {
        ...sharedToken,
        colorBgLayout: PALETTE.neutral.gray1,
        colorBgContainer: PALETTE.neutral.white,
        colorText: PALETTE.neutral.gray8,
        colorTextSecondary: PALETTE.neutral.gray5,
        colorBorder: PALETTE.neutral.gray3,
    },
    components: {
        Layout: {
            headerBg: PALETTE.neutral.white,
            siderBg: PALETTE.neutral.white,
            bodyBg: PALETTE.neutral.gray1,
            headerHeight: 56,
        },
        Menu: {
            itemSelectedBg: '#e6f0ff',
            itemSelectedColor: PALETTE.primaryActive,
        },
    },
};
export const darkTheme = {
    algorithm: antdTheme.darkAlgorithm,
    token: {
        ...sharedToken,
        colorBgLayout: PALETTE.neutral.black,
        colorBgContainer: PALETTE.neutral.gray8,
        colorText: PALETTE.neutral.gray1,
        colorTextSecondary: PALETTE.neutral.gray4,
        colorBorder: PALETTE.neutral.gray6,
    },
    components: {
        Layout: {
            headerBg: PALETTE.neutral.gray8,
            siderBg: PALETTE.neutral.gray8,
            bodyBg: PALETTE.neutral.black,
            headerHeight: 56,
        },
        Menu: {
            itemSelectedBg: '#11335c',
            itemSelectedColor: PALETTE.primaryHover,
        },
    },
};
/** Resolve the active {@link ThemeConfig} for a given mode. */
export const getThemeConfig = (mode) => mode === 'dark' ? darkTheme : lightTheme;
