/**
 * Authentication API service.
 *
 * Thin wrappers over the `/auth` endpoints defined in
 * `backend/app/api/v1/auth.py`.
 */
import { apiClient } from './apiClient';
export const authService = {
    register: (data) => apiClient.post('/auth/register', data, { skipAuth: true, handleUnauthorized: false }),
    login: (data) => apiClient.post('/auth/login', data, { skipAuth: true, handleUnauthorized: false }),
    logout: () => apiClient.post('/auth/logout'),
    requestPasswordReset: (data) => apiClient.post('/auth/password/reset-request', data, { skipAuth: true, handleUnauthorized: false }),
    resetPassword: (data) => apiClient.post('/auth/password/reset', data, { skipAuth: true, handleUnauthorized: false }),
};
