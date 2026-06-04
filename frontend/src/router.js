import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Application route configuration.
 *
 * Public routes: /login, /register.
 * Protected routes (guarded by <ProtectedRoute>): all primary modules rendered
 * inside the <AppLayout> shell. Unauthenticated access to protected routes
 * redirects to /login (Req 8.14); access to all modules is within 2 clicks
 * from the persistent navigation (Req 12.18).
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from './components/Layout/AppLayout';
import ProtectedRoute from './components/Auth/ProtectedRoute';
import Login from './pages/Auth/Login';
import Register from './pages/Auth/Register';
import Dashboard from './pages/Dashboard/Dashboard';
import AnalysisPage from './pages/Analysis';
import LiteraturePage from './pages/Literature';
import { TranslationPage, TranslationHistoryPage } from './pages/Translation';
import HistoryPage from './pages/History';
export const router = createBrowserRouter([
    {
        path: '/login',
        element: _jsx(Login, {}),
    },
    {
        path: '/register',
        element: _jsx(Register, {}),
    },
    {
        element: _jsx(ProtectedRoute, {}),
        children: [
            {
                element: _jsx(AppLayout, {}),
                children: [
                    { index: true, element: _jsx(Navigate, { to: "/dashboard", replace: true }) },
                    { path: 'dashboard', element: _jsx(Dashboard, {}) },
                    {
                        path: 'analysis',
                        element: _jsx(AnalysisPage, {}),
                    },
                    {
                        path: 'literature',
                        element: _jsx(LiteraturePage, {}),
                    },
                    {
                        path: 'translation',
                        element: _jsx(TranslationPage, {}),
                    },
                    {
                        path: 'history',
                        element: _jsx(HistoryPage, {}),
                    },
                    {
                        path: 'translation-history',
                        element: _jsx(TranslationHistoryPage, {}),
                    },
                ],
            },
        ],
    },
    {
        path: '*',
        element: _jsx(Navigate, { to: "/dashboard", replace: true }),
    },
]);
