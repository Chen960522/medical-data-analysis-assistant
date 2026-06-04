/**
 * Data file API service.
 *
 * Wraps the `/data` endpoints defined in `backend/app/api/v1/data.py`.
 * The upload method reports progress via XHR so the UI can show an upload
 * progress bar (Req 1.x, 11.x upload feedback).
 */

import { API_BASE, apiClient, buildXhrError } from './apiClient';
import { getToken } from './tokenStorage';
import type {
  DataFile,
  DataFileListResponse,
  DataPreviewResponse,
  DataQualityResponse,
  UploadResponse,
} from '../types/data';

export interface UploadProgress {
  /** 0-100 percentage. */
  percent: number;
  loaded: number;
  total: number;
}

export const dataService = {
  /**
   * Upload a data file with progress reporting.
   *
   * Uses XMLHttpRequest because the fetch API does not expose upload progress
   * events. Resolves with the created DataFile record.
   */
  upload(
    file: File,
    onProgress?: (progress: UploadProgress) => void,
    signal?: AbortSignal,
  ): Promise<UploadResponse> {
    return new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${API_BASE}/data/upload`);
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
            resolve(JSON.parse(xhr.responseText) as UploadResponse);
          } catch {
            reject(new Error('无法解析服务器响应'));
          }
        } else {
          // Delegate to the shared interceptor so the XHR upload handles auth
          // expiry (401 → redirect) and permission denial (403) consistently
          // with the fetch pipeline.
          reject(buildXhrError(xhr.status, xhr.responseText, `上传失败 (${xhr.status})`));
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

  listFiles: () => apiClient.get<DataFileListResponse>('/data/files'),

  /** Fetch the first-10-rows preview for a file (Req 2.2). */
  getPreview: (fileId: string) =>
    apiClient.get<DataPreviewResponse>(`/data/files/${fileId}/preview`),

  /** Fetch the data quality report for a file (Req 2.6). */
  getQuality: (fileId: string) =>
    apiClient.get<DataQualityResponse>(`/data/files/${fileId}/quality`),

  deleteFile: (fileId: string) => apiClient.delete<void>(`/data/files/${fileId}`),
};

export type { DataFile };
