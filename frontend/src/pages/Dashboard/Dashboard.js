import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Main dashboard page.
 *
 * Landing page after login. Provides the data upload entry point and a brief
 * orientation to the platform's primary modules. Full analytics widgets are
 * added in later tasks; this establishes the framework and demonstrates the
 * shared design-system components.
 */
import { Button, Card, Col, Row, Space } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PageContainer } from '../../components/Common';
import { FileUpload } from '../../components/Upload/FileUpload';
import { SPACING } from '../../theme/tokens';
export function Dashboard() {
    const navigate = useNavigate();
    return (_jsx(PageContainer, { title: "\u4EEA\u8868\u76D8", description: "\u6B22\u8FCE\u4F7F\u7528\u533B\u5B66\u6570\u636E\u5206\u6790\u52A9\u624B\u3002\u4E0A\u4F20\u6570\u636E\u6587\u4EF6\u5F00\u59CB AI \u667A\u80FD\u5206\u6790\u3002", children: _jsxs(Row, { gutter: [SPACING.lg, SPACING.lg], children: [_jsx(Col, { xs: 24, lg: 14, children: _jsxs(Card, { title: "\u4E0A\u4F20\u533B\u5B66\u6570\u636E", variant: "outlined", children: [_jsx(FileUpload, { onUploaded: () => navigate('/analysis') }), _jsx(Space, { style: { marginTop: SPACING.md }, children: _jsx(Button, { type: "primary", icon: _jsx(ArrowRightOutlined, {}), onClick: () => navigate('/analysis'), children: "\u524D\u5F80\u6570\u636E\u5206\u6790" }) })] }) }), _jsx(Col, { xs: 24, lg: 10, children: _jsx(Card, { title: "\u5FEB\u901F\u5F00\u59CB", variant: "outlined", children: _jsxs("ul", { style: { paddingInlineStart: SPACING.lg, margin: 0, lineHeight: 2 }, children: [_jsx("li", { children: "\u4E0A\u4F20 CSV\u3001Excel \u6216 JSON \u683C\u5F0F\u7684\u533B\u5B66\u6570\u636E" }), _jsx("li", { children: "\u7531 AI \u81EA\u52A8\u8FDB\u884C\u591A\u7EF4\u5EA6\u7EDF\u8BA1\u5206\u6790" }), _jsx("li", { children: "\u67E5\u770B\u53EF\u89C6\u5316\u56FE\u8868\u5E76\u5BFC\u51FA\u5206\u6790\u62A5\u544A" }), _jsx("li", { children: "\u68C0\u7D22 CNKI / PubMed \u6587\u732E\u5E76\u7FFB\u8BD1 PDF \u6587\u732E" })] }) }) })] }) }));
}
export default Dashboard;
