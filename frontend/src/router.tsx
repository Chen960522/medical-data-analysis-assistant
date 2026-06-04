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
    element: <Login />,
  },
  {
    path: '/register',
    element: <Register />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: <Dashboard /> },
          {
            path: 'analysis',
            element: <AnalysisPage />,
          },
          {
            path: 'literature',
            element: <LiteraturePage />,
          },
          {
            path: 'translation',
            element: <TranslationPage />,
          },
          {
            path: 'history',
            element: <HistoryPage />,
          },
          {
            path: 'translation-history',
            element: <TranslationHistoryPage />,
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
]);
