import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Application root.
 *
 * Wires together the theme provider (light/dark, Req 12.26-12.28), the Ant
 * Design App context (for message/notification/modal APIs), and the router.
 * Registers a global 401 handler so an expired session redirects to login
 * (Req 8.14).
 */
import { useEffect } from 'react';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { getThemeConfig } from './theme/themeConfig';
import { useThemeStore } from './stores/themeStore';
import { useAuthStore } from './stores/authStore';
import { setUnauthorizedHandler } from './services/apiClient';
function App() {
    const mode = useThemeStore((state) => state.mode);
    const syncFromStorage = useAuthStore((state) => state.syncFromStorage);
    useEffect(() => {
        // On a 401 the token is cleared; sync the store so the route guard
        // redirects the user to the login page (Req 8.14).
        setUnauthorizedHandler(() => {
            syncFromStorage();
        });
        return () => setUnauthorizedHandler(null);
    }, [syncFromStorage]);
    return (_jsx(ConfigProvider, { locale: zhCN, theme: getThemeConfig(mode), children: _jsx(AntApp, { children: _jsx(RouterProvider, { router: router }) }) }));
}
export default App;
