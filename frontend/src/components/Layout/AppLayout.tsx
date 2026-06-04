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
import {
  BulbOutlined,
  BulbFilled,
  HomeOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
} from '@ant-design/icons';
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
  const activeItem = useMemo(
    () => NAV_ITEMS.find((item) => location.pathname.startsWith(item.path)),
    [location.pathname],
  );
  const selectedKeys = activeItem ? [activeItem.key] : [];

  // Build breadcrumb trail (Req 12.20).
  const breadcrumbItems = useMemo(() => {
    const items = [
      {
        title: (
          <Link to="/dashboard" aria-label="返回首页">
            <HomeOutlined />
          </Link>
        ),
      },
    ];
    const label = PATH_LABEL_MAP[activeItem?.path ?? ''];
    if (label) {
      items.push({ title: <span>{label}</span> });
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
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: handleLogout,
      },
    ],
  };

  const menuItems = NAV_ITEMS.map((item) => ({
    key: item.key,
    icon: item.icon,
    label: <Link to={item.path}>{item.label}</Link>,
  }));

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        breakpoint="lg"
        width={220}
        aria-label="主导航"
      >
        <div
          style={{
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
          }}
        >
          {collapsed ? '医析' : '医学数据分析助手'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: `0 ${SPACING.md}px`,
            borderBottom: '1px solid rgba(0,0,0,0.06)',
          }}
        >
          <Button
            type="text"
            aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((prev) => !prev)}
            style={{ width: 44, height: 44 }}
          />

          <Space size="middle">
            <Tooltip title={mode === 'dark' ? '切换到亮色主题' : '切换到暗色主题'}>
              <Button
                type="text"
                aria-label="切换主题"
                icon={mode === 'dark' ? <BulbFilled /> : <BulbOutlined />}
                onClick={toggleMode}
                style={{ width: 44, height: 44 }}
              />
            </Tooltip>

            <Dropdown menu={accountMenu} trigger={['click']}>
              <Button type="text" style={{ height: 44 }} aria-label="账户菜单">
                <Space>
                  <UserOutlined />
                  <Text>{email ?? '当前用户'}</Text>
                </Space>
              </Button>
            </Dropdown>
          </Space>
        </Header>

        <div style={{ padding: `${SPACING.md}px ${SPACING.lg}px 0` }}>
          <Breadcrumb items={breadcrumbItems} />
        </div>

        <Content style={{ margin: 0 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

export default AppLayout;
