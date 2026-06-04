/**
 * Authentication state store.
 *
 * Tracks the authenticated session client-side. The bearer token and its expiry
 * are persisted via tokenStorage; this store exposes the derived auth state plus
 * login/logout actions for the UI and route guard (Req 8.8, 8.14, 8.15).
 */
import { create } from 'zustand';
import { authService } from '../services/authService';
import { clearToken, getToken, hasValidToken, saveToken } from '../services/tokenStorage';
const EMAIL_KEY = 'mdaa_user_email';
export const useAuthStore = create((set) => ({
    isAuthenticated: hasValidToken(),
    email: localStorage.getItem(EMAIL_KEY),
    login: async (credentials) => {
        const response = await authService.login(credentials);
        saveToken(response.access_token, response.expires_in);
        localStorage.setItem(EMAIL_KEY, credentials.email);
        set({ isAuthenticated: true, email: credentials.email });
    },
    logout: async () => {
        try {
            await authService.logout();
        }
        catch {
            // Even if the server call fails, clear local session.
        }
        clearToken();
        localStorage.removeItem(EMAIL_KEY);
        set({ isAuthenticated: false, email: null });
    },
    syncFromStorage: () => {
        const valid = getToken() !== null && hasValidToken();
        set({
            isAuthenticated: valid,
            email: valid ? localStorage.getItem(EMAIL_KEY) : null,
        });
    },
}));
