/**
 * Analysis TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/analysis.py` for the
 * Agent-driven analysis API (start, status, results, charts, dimensions,
 * history). Supports the data-analysis dashboard (Req 2.2, 2.6, 3.1-3.8,
 * 9.19-9.22).
 */

import type { ChartData } from '../components/Charts';

/** A generated chart, identical in shape to the Charts library `ChartData`. */
export type Chart = ChartData;

/** Analysis session lifecycle status as returned by the backend. */
export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed' | string;

/** An analysis session record. */
export interface AnalysisSession {
  id: string;
  file_id: string;
  status: AnalysisStatus;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

/**
 * A single analysis result row.
 *
 * `result_type` is a free string; known values (`descriptive`, `correlation`,
 * `outlier`, `trend`, `group_comparison`) map to Chinese section titles, with a
 * fallback to the raw type.
 */
export interface AnalysisResult {
  id: string;
  result_type: string;
  result_data: Record<string, unknown>;
}

/** A structured analysis report. */
export interface Report {
  id: string;
  title: string;
  content: Record<string, unknown>;
}

/** Distinguishes system-generated dimensions from user-requested ones (Req 9.22). */
export type DimensionType = 'system' | 'user';

/** An active analysis dimension. */
export interface Dimension {
  id: string;
  name: string;
  dimension_type: DimensionType;
  config?: Record<string, unknown> | null;
}

/** Progress/status of an in-flight or completed analysis (Req 3.7). */
export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
  stage: string;
  /** 0-100 percentage. */
  progress: number;
}

/** Response from `POST /analysis/start`. */
export interface StartAnalysisResponse {
  session: AnalysisSession;
  results: AnalysisResult[];
  charts: Chart[];
  report?: Report | null;
}

/** Response from `GET /analysis/{id}/results`. */
export interface AnalysisResultsResponse {
  session: AnalysisSession;
  results: AnalysisResult[];
  report?: Report | null;
}

/** Response from `GET /analysis/{id}/charts`. */
export interface ChartsResponse {
  analysis_id: string;
  charts: Chart[];
  total: number;
}

/** Response from `GET /analysis/history`. */
export interface AnalysisHistoryResponse {
  sessions: AnalysisSession[];
  total: number;
}

/** Request body for `POST /analysis/{id}/dimensions`. */
export interface DimensionRequest {
  description: string;
  name?: string;
  config?: Record<string, unknown>;
}

/** Response from `POST /analysis/{id}/dimensions`. */
export interface DimensionResultResponse {
  dimension: Dimension;
  results: AnalysisResult[];
  charts: Chart[];
}
