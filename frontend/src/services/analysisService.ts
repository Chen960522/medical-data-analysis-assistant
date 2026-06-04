/**
 * Analysis API service.
 *
 * Wraps the `/analysis` endpoints defined in `backend/app/api/v1/analysis.py`
 * for the Agent-driven analysis lifecycle: starting an analysis, polling
 * status, fetching results/charts, managing dimensions, listing history, and
 * deleting records (Req 3.1-3.8, 6.1-6.5, 9.19-9.22).
 */

import { apiClient } from './apiClient';
import type {
  AnalysisHistoryResponse,
  AnalysisResultsResponse,
  AnalysisStatusResponse,
  ChartsResponse,
  DimensionRequest,
  DimensionResultResponse,
  StartAnalysisResponse,
} from '../types/analysis';

export const analysisService = {
  /** Start an Agent-driven analysis for an uploaded data file (Req 3.1-3.7). */
  start: (fileId: string) =>
    apiClient.post<StartAnalysisResponse>('/analysis/start', { file_id: fileId }),

  /** Get the user's analysis history sorted by date descending (Req 6.2). */
  history: () => apiClient.get<AnalysisHistoryResponse>('/analysis/history'),

  /** Query analysis progress for a session (Req 3.7). */
  status: (analysisId: string) =>
    apiClient.get<AnalysisStatusResponse>(`/analysis/${analysisId}/status`),

  /** Get the persisted analysis results for a session (Req 3.1-3.5, 6.3). */
  results: (analysisId: string) =>
    apiClient.get<AnalysisResultsResponse>(`/analysis/${analysisId}/results`),

  /** Get the persisted charts for a session (Req 4.1-4.6, 6.3). */
  charts: (analysisId: string) =>
    apiClient.get<ChartsResponse>(`/analysis/${analysisId}/charts`),

  /** Add a user-requested analysis dimension via the Agent (Req 3.8, 9.19, 9.20). */
  addDimension: (analysisId: string, body: DimensionRequest) =>
    apiClient.post<DimensionResultResponse>(`/analysis/${analysisId}/dimensions`, body),

  /** Remove an analysis dimension from a session (Req 9.20, 9.21). */
  removeDimension: (analysisId: string, dimId: string) =>
    apiClient.delete<void>(`/analysis/${analysisId}/dimensions/${dimId}`),

  /** Delete an analysis record and its associated data (Req 6.4). */
  remove: (analysisId: string) => apiClient.delete<void>(`/analysis/${analysisId}`),
};
