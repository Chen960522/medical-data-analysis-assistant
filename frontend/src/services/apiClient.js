/**
 * Core HTTP API client.
 *
 * Centralizes communication with the FastAPI backend:
 * - Injects the bearer token into the Authorization header (Req 8.12).
 * - Sends cookies (the backend also uses an HTTP-only session cookie).
 * - Normalizes backend error payloads ({ detail: string }) into ApiError.
 * - On a 401 response, clears the token and triggers the expiry handler so the
 *   UI can redirect the user to the login page (Req 8.14).
 */
import { clearToken, getToken } from './tokenStorage';
/** Base path for API v1. Proxied to the backend by Vite in development. */
export const API_BASE = '/api/v1';
export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        Object.defineProperty(this, "status", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        this.name = 'ApiError';
        this.status = status;
    }
}
let unauthorizedHandler = null;
export function setUnauthorizedHandler(handler) {
    unauthorizedHandler = handler;
}
async function parseError(response) {
    try {
        const data = await response.json();
        if (data && typeof data.detail === 'string') {
            return data.detail;
        }
        if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
            return data.detail[0].msg;
        }
    }
    catch {
        // Non-JSON error body; fall through to a generic message.
    }
    return `请求失败 (${response.status})`;
}
async function request(path, options = {}) {
    const { method = 'GET', body, skipAuth = false, handleUnauthorized = true, signal } = options;
    const headers = {};
    let payload;
    if (body instanceof FormData) {
        payload = body;
    }
    else if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
    }
    if (!skipAuth) {
        const stored = getToken();
        if (stored) {
            headers.Authorization = `Bearer ${stored.token}`;
        }
    }
    const response = await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: payload,
        credentials: 'include',
        signal,
    });
    if (response.status === 401 && handleUnauthorized) {
        clearToken();
        if (unauthorizedHandler) {
            unauthorizedHandler();
        }
        throw new ApiError('登录已过期，请重新登录', 401);
    }
    if (!response.ok) {
        throw new ApiError(await parseError(response), response.status);
    }
    if (response.status === 204) {
        return undefined;
    }
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
        return (await response.json());
    }
    return (await response.text());
}
export const apiClient = {
    get: (path, options) => request(path, { ...options, method: 'GET' }),
    post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
    put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
    delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
};
