/**
 * Authentication API service.
 *
 * Thin wrappers over the `/auth` endpoints defined in
 * `backend/app/api/v1/auth.py`.
 */

import { apiClient } from './apiClient';
import type {
  AuthResponse,
  LoginRequest,
  LoginResponse,
  PasswordReset,
  PasswordResetRequest,
  RegisterRequest,
} from '../types/auth';

export const authService = {
  register: (data: RegisterRequest) =>
    apiClient.post<AuthResponse>('/auth/register', data, { skipAuth: true }),

  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', data, { skipAuth: true }),

  logout: () => apiClient.post<AuthResponse>('/auth/logout'),

  requestPasswordReset: (data: PasswordResetRequest) =>
    apiClient.post<AuthResponse>('/auth/password/reset-request', data, { skipAuth: true }),

  resetPassword: (data: PasswordReset) =>
    apiClient.post<AuthResponse>('/auth/password/reset', data, { skipAuth: true }),
};
