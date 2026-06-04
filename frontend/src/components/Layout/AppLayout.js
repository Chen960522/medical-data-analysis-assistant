import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Application shell layout.
 *
 * Provides the persistent navigation structure shared across all pages:
 * - A top header with the brand, theme toggle, and account/logout area
 *   in a consistent location (Req 12.21, 12.26).
 * - A collapsible sidebar menu giving 2-click access to every primary module
 *   (Req 12.18) with active-item highlighting (Req 12.19).
 * - Breadcrumb navigation for orientation on nested pages (Req 12.20).
 *
 * The layout adapts to tablet viewports by auto-collapsing the sidebar
 * (Req 12.5, 12.6) and renders content via <Outlet />.
 */
import { useEffect, useMemo, useState } from 'react';
import { Breadcrumb, Button, Dropdown, Layout, Menu, Space, Tooltip, Typography } from 'antd';
import { BulbOutlined, BulbFilled, HomeOutlined, LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined, UserOutlined, } from '@ant-design/icons';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { NAV_ITEMS, PATH_LABEL_MAP } from '../../config/navigation';
import { useResponsive } from '../../hooks/useResponsive';
import { useNotify } from '../../hooks/useNotify';
import { useAuthStore } from '../../stores/authStore';
import { useThemeStore } from '../../stores/themeStore';
import { SPACING } from '../../theme/tokens';
const { Header, Sider, Content } = Layout;
const { Text } = Typography;
export function AppLayout() {
    const location = useLocation();
    const navigate = useNavigate();
    const notify = useNotify();
    const { isTablet } = useResponsive();
    const { mode, toggleMode } = useThemeStore();
    const { email, logout } = useAuthStore();
    const [collapsed, setCollapsed] = useState(false);
    // Auto-collapse the sidebar on tablet viewports (Req 12.6).
    useEffect(() => {
        setCollapsed(isTablet);
    }, [isTablet]);
    // Determine the active nav item from the current path (Req 12.19).
    const activeItem = useMemo(() => NAV_ITEMS.find((item) => location.pathname.startsWith(item.path)), [location.pathname]);
    const selectedKeys = activeItem ? [activeItem.key] : [];
    // Build breadcrumb trail (Req 12.20).
    const breadcrumbItems = useMemo(() => {
        const items = [
            {
                title: (_jsx(Link, { to: "/dashboard", "aria-label": "\u8FD4\u56DE\u9996\u9875", children: _jsx(HomeOutlined, {}) })),
            },
        ];
        const label = PATH_LABEL_MAP[activeItem?.path ?? ''];
        if (label) {
            items.push({ title: _jsx("span", { children: label }) });
        }
        return items;
    }, [activeItem]);
    const handleLogout = async () => {
        await logout();
        notify.success('已安全退出登录');
        navigate('/login', { replace: true });
    };
    const accountMenu = {
        items: [
            {
                key: 'logout',
                icon: _jsx(LogoutOutlined, {}),
                label: '退出登录',
                onClick: handleLogout,
            },
        ],
    };
    const menuItems = NAV_ITEMS.map((item) => ({
        key: item.key,
        icon: item.icon,
        label: _jsx(Link, { to: item.path, children: item.label }),
    }));
    return (_jsxs(Layout, { style: { minHeight: '100vh' }, children: [_jsxs(Sider, { collapsible: true, collapsed: collapsed, onCollapse: setCollapsed, trigger: null, breakpoint: "lg", width: 220, "aria-label": "\u4E3B\u5BFC\u822A", children: [_jsx("div", { style: {
                            height: 56,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: `0 ${SPACING.md}px`,
                            fontWeight: 600,
                            fontSize: 16,
                            color: 'var(--ant-color-primary, #1677ff)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                        }, children: collapsed ? '医析' : '医学数据分析助手' }), _jsx(Menu, { mode: "inline", selectedKeys: selectedKeys, items: menuItems, style: { borderInlineEnd: 'none' } })] }), _jsxs(Layout, { children: [_jsxs(Header, { style: {
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: `0 ${SPACING.md}px`,
                            borderBottom: '1px solid rgba(0,0,0,0.06)',
                        }, children: [_jsx(Button, { type: "text", "aria-label": collapsed ? '展开侧边栏' : '收起侧边栏', icon: collapsed ? _jsx(MenuUnfoldOutlined, {}) : _jsx(MenuFoldOutlined, {}), onClick: () => setCollapsed((prev) => !prev), style: { width: 44, height: 44 } }), _jsxs(Space, { size: "middle", children: [_jsx(Tooltip, { title: mode === 'dark' ? '切换到亮色主题' : '切换到暗色主题', children: _jsx(Button, { type: "text", "aria-label": "\u5207\u6362\u4E3B\u9898", icon: mode === 'dark' ? _jsx(BulbFilled, {}) : _jsx(BulbOutlined, {}), onClick: toggleMode, style: { width: 44, height: 44 } }) }), _jsx(Dropdown, { menu: accountMenu, trigger: ['click'], children: _jsx(Button, { type: "text", style: { height: 44 }, "aria-label": "\u8D26\u6237\u83DC\u5355", children: _jsxs(Space, { children: [_jsx(UserOutlined, {}), _jsx(Text, { children: email ?? '当前用户' })] }) }) })] })] }), _jsx("div", { style: { padding: `${SPACING.md}px ${SPACING.lg}px 0` }, children: _jsx(Breadcrumb, { items: breadcrumbItems }) }), _jsx(Content, { style: { margin: 0 }, children: _jsx(Outlet, {}) })] })] }));
}
export default AppLayout;
