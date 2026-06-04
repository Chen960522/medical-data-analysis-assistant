/**
 * PDF translation API service.
 *
 * Wraps the `/translation` endpoints defined in
 * `backend/app/api/v1/translation.py` for the Agent-driven PDF literature
 * translation module — Req 11.1-11.50:
 * - `upload`: PDF upload (PDF only, ≤ 50MB) with progress reporting.
 * - `translate`: trigger full-document translation (synchronous on the backend).
 * - `getStatus` / `getResult`: poll progress and fetch the bilingual result.
 * - `getDownloadUrl`: resolve a presigned download URL (PDF/Word, bilingual/translated).
 * - `getHistory` / `deleteRecord`: translation-history management.
 *
 * The upload uses a raw `XMLHttpRequest` (modeled on `dataService.upload`)
 * because the fetch API does not expose upload progress events; it posts a
 * `FormData` with field name `file` and the bearer token from `getToken()`.
 * The upload targets `/translation/upload`, distinct from the data-upload
 * endpoint (Req 11.1).
 */
import { API_BASE, apiClient } from './apiClient';
import { getToken } from './tokenStorage';
/** Build a query string from a set of params (drops empty values). */
function buildQuery(params) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            search.append(key, value);
        }
    });
    const query = search.toString();
    return query ? `?${query}` : '';
}
export const translationService = {
    /**
     * Upload a PDF for translation with progress reporting (Req 11.1-11.7).
     *
     * Uses XMLHttpRequest to expose upload progress events. Resolves with the
     * created TranslationRecord summary.
     */
    upload(file, onProgress, signal) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();
            formData.append('file', file);
            xhr.open('POST', `${API_BASE}/translation/upload`);
            xhr.withCredentials = true;
            const stored = getToken();
            if (stored) {
                xhr.setRequestHeader('Authorization', `Bearer ${stored.token}`);
            }
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable && onProgress) {
                    onProgress({
                        percent: Math.round((event.loaded / event.total) * 100),
                        loaded: event.loaded,
                        total: event.total,
                    });
                }
            };
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    }
                    catch {
                        reject(new Error('无法解析服务器响应'));
                    }
                }
                else {
                    let detail = `上传失败 (${xhr.status})`;
                    try {
                        const parsed = JSON.parse(xhr.responseText);
                        if (parsed?.detail) {
                            detail = typeof parsed.detail === 'string' ? parsed.detail : detail;
                        }
                    }
                    catch {
                        // keep generic message
                    }
                    reject(new Error(detail));
                }
            };
            xhr.onerror = () => reject(new Error('网络错误，上传失败'));
            xhr.onabort = () => reject(new DOMException('上传已取消', 'AbortError'));
            if (signal) {
                signal.addEventListener('abort', () => xhr.abort());
            }
            xhr.send(formData);
        });
    },
    /**
     * Trigger full-document translation (Req 11.21).
     *
     * This endpoint is synchronous on the backend (it parses + translates and
     * returns the full result), so it may take a while; callers should show a
     * progress / loading indicator while awaiting. An optional `source_language`
     * override takes precedence over auto-detection (Req 11.19).
     */
    translate: (translationId, body, signal) => apiClient.post(`/translation/${translationId}/translate`, body ?? {}, { signal }),
    /** Query translation progress + detected languages (Req 11.28). */
    getStatus: (translationId, signal) => apiClient.get(`/translation/${translationId}/status`, { signal }),
    /** Fetch the bilingual Translation_Result (Req 11.30-11.34); 404 if not translated. */
    getResult: (translationId, signal) => apiClient.get(`/translation/${translationId}/result`, { signal }),
    /** Resolve a presigned download URL for the exported document (Req 11.37-11.41). */
    getDownloadUrl: (translationId, format, mode) => apiClient.get(`/translation/${translationId}/download${buildQuery({ format, mode })}`),
    /** List the user's translation history, newest first (Req 11.43, 11.44). */
    getHistory: () => apiClient.get('/translation/history'),
    /** Delete a translation record and its associated files (Req 11.46, 11.47). */
    deleteRecord: (translationId) => apiClient.delete(`/translation/${translationId}`),
};
