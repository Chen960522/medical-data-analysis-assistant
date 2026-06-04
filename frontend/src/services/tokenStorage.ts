/**
 * JWT token storage utilities.
 *
 * The backend issues a JWT and also sets an HTTP-only secure cookie
 * (`backend/app/api/v1/auth.py`). The HTTP-only cookie cannot be read by JS, so
 * we additionally persist the bearer token client-side to drive the
 * Authorization header and to track expiry for proactive redirect-on-expiry
 * (Req 8.12, 8.14).
 */

const TOKEN_KEY = 'mdaa_access_token';
const EXPIRY_KEY = 'mdaa_token_expiry';

export interface StoredToken {
  token: string;
  /** Absolute expiry time in epoch milliseconds. */
  expiresAt: number;
}

export function saveToken(token: string, expiresInSeconds: number): void {
  const expiresAt = Date.now() + expiresInSeconds * 1000;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EXPIRY_KEY, String(expiresAt));
}

export function getToken(): StoredToken | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const expiryRaw = localStorage.getItem(EXPIRY_KEY);
  if (!token || !expiryRaw) {
    return null;
  }
  const expiresAt = Number(expiryRaw);
  if (Number.isNaN(expiresAt)) {
    return null;
  }
  return { token, expiresAt };
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRY_KEY);
}

/** Returns true when a valid, unexpired token is present. */
export function hasValidToken(): boolean {
  const stored = getToken();
  if (!stored) {
    return false;
  }
  return stored.expiresAt > Date.now();
}
