/**
 * Core HTTP API client.
 *
 * Centralizes communication with the FastAPI backend:
 * - Injects the bearer token into the Authorization header (Req 8.12).
 * - Sends cookies (the backend also uses an HTTP-only session cookie).
 * - Normalizes backend error payloads ({ detail: string }) into ApiError.
 * - Unified error interception (task 15.1):
 *   - Network errors (fetch rejection / no response) surface a user-friendly
 *     Chinese ApiError (status 0) instead of an unhandled raw TypeError.
 *   - Auth expiry (401) clears the token and triggers the expiry handler so the
 *     UI can redirect the user to the login page (Req 8.14).
 *   - Permission denied (403) surfaces a clear "无权访问" Chinese message and is
 *     NOT treated as a 401 redirect (Req 8.21).
 */

import { clearToken, getToken } from './tokenStorage';

/** Base path for API v1. Proxied to the backend by Vite in development. */
export const API_BASE = '/api/v1';

/**
 * Synthetic status used for network/transport errors (no HTTP response was
 * received, e.g. the backend is unreachable or the request was blocked).
 */
export const NETWORK_ERROR_STATUS = 0;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  /** True when no HTTP response was received (network/transport failure). */
  get isNetworkError(): boolean {
    return this.status === NETWORK_ERROR_STATUS;
  }
}

/** Handler invoked when an authenticated request returns 401 (token expired). */
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** When true, omit the Authorization header (used for login/register). */
  skipAuth?: boolean;
  /** Set to false for endpoints that should not redirect on 401. */
  handleUnauthorized?: boolean;
  signal?: AbortSignal;
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (data && typeof data.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      return data.detail[0].msg as string;
    }
  } catch {
    // Non-JSON error body; fall through to a generic message.
  }
  return `请求失败 (${response.status})`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, skipAuth = false, handleUnauthorized = true, signal } = options;

  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;

  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  if (!skipAuth) {
    const stored = getToken();
    if (stored) {
      headers.Authorization = `Bearer ${stored.token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: payload,
      credentials: 'include',
      signal,
    });
  } catch (err) {
    // A rejected fetch means no HTTP response was received. Preserve genuine
    // aborts (so callers can ignore cancelled requests) but normalize all other
    // transport failures into a user-friendly Chinese network error.
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err;
    }
    throw new ApiError('网络连接失败，请检查网络后重试', NETWORK_ERROR_STATUS);
  }

  if (response.status === 401 && handleUnauthorized) {
    clearToken();
    if (unauthorizedHandler) {
      unauthorizedHandler();
    }
    throw new ApiError('登录已过期，请重新登录', 401);
  }

  // Permission denied: the user is authenticated but not allowed to access the
  // resource. Surface a clear Chinese message and explicitly do NOT redirect to
  // login (Req 8.21).
  if (response.status === 403) {
    const detail = await parseError(response);
    // Prefer a friendly Chinese message; keep any specific backend detail when
    // it is already localized (non-ASCII), otherwise use the generic notice.
    const message = /[\u4e00-\u9fff]/.test(detail) ? detail : '无权访问该资源';
    throw new ApiError(message, 403);
  }

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
};

/** Extract a `detail` message from a raw XHR JSON response body. */
function parseXhrDetail(responseText: string): string {
  try {
    const parsed = JSON.parse(responseText);
    if (parsed && typeof parsed.detail === 'string') {
      return parsed.detail;
    }
    if (Array.isArray(parsed?.detail) && parsed.detail[0]?.msg) {
      return parsed.detail[0].msg as string;
    }
  } catch {
    // Non-JSON body; fall through to an empty detail.
  }
  return '';
}

/**
 * Build an {@link ApiError} from a non-2xx XHR response, applying the same
 * unified interception as the fetch pipeline.
 *
 * The XHR-based uploads (`dataService.upload` / `translationService.upload`)
 * cannot use the fetch-based {@link request} (which lacks upload-progress
 * events), so they delegate error handling here to stay consistent:
 * - 401: clears the token and triggers the expiry handler (redirect to login).
 * - 403: surfaces a clear Chinese "无权访问" message (no redirect).
 * - otherwise: the backend detail, or a generic upload-failure message.
 *
 * @param fallback Generic message used when the body carries no detail.
 */
export function buildXhrError(status: number, responseText: string, fallback: string): ApiError {
  if (status === 401) {
    clearToken();
    if (unauthorizedHandler) {
      unauthorizedHandler();
    }
    return new ApiError('登录已过期，请重新登录', 401);
  }

  const detail = parseXhrDetail(responseText);

  if (status === 403) {
    const message = /[\u4e00-\u9fff]/.test(detail) ? detail : '无权访问该资源';
    return new ApiError(message, 403);
  }

  return new ApiError(detail || fallback, status);
}
