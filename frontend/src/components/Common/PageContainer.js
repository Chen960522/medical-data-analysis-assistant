import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Page content container.
 *
 * Provides consistent page padding and an optional title/description header
 * using the shared 8px spacing grid (Req 12.11) and constrained typography
 * (Req 12.10). Children are rendered within a max-width column that adapts to
 * tablet and desktop viewports (Req 12.5).
 */
import { Typography } from 'antd';
import { SPACING } from '../../theme/tokens';
const { Title, Paragraph } = Typography;
export function PageContainer({ title, description, extra, children, style }) {
    return (_jsxs("div", { style: { padding: SPACING.lg, ...style }, children: [(title || extra) && (_jsxs("div", { style: {
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: SPACING.md,
                    marginBottom: SPACING.md,
                    flexWrap: 'wrap',
                }, children: [_jsxs("div", { children: [title ? (_jsx(Title, { level: 2, style: { marginBottom: description ? SPACING.xs : 0 }, children: title })) : null, description ? (_jsx(Paragraph, { type: "secondary", style: { marginBottom: 0 }, children: description })) : null] }), extra ? _jsx("div", { children: extra }) : null] })), children] }));
}
export default PageContainer;
