import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Route guard.
 *
 * Redirects unauthenticated users to the login page, preserving the originally
 * requested location so they can be returned there after signing in (Req 8.14).
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
export function ProtectedRoute() {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
    const location = useLocation();
    if (!isAuthenticated) {
        return _jsx(Navigate, { to: "/login", replace: true, state: { from: location } });
    }
    return _jsx(Outlet, {});
}
export default ProtectedRoute;
