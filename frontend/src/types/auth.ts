/**
 * Authentication-related TypeScript types.
 *
 * These mirror the backend request/response schemas in
 * `backend/app/schemas/auth.py` to keep the API contract in sync.
 */

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  /** Token expiration in seconds. */
  expires_in: number;
}

export interface AuthResponse {
  message: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordReset {
  token: string;
  new_password: string;
}
