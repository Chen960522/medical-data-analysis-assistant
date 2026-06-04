/**
 * Analysis report API service.
 *
 * Wraps the `/reports` endpoints defined in `backend/app/api/v1/reports.py` for
 * the Agent-driven report module: generating a structured Analysis_Report for an
 * analysis session and resolving a presigned download URL for the exported
 * report file (PDF / Word) — Req 5.5-5.7.
 */

import { apiClient } from './apiClient';
import type {
  GenerateReportRequest,
  ReportDownloadResponse,
  ReportFormat,
  ReportResponse,
} from '../types/reports';

export const reportsService = {
  /**
   * Generate a structured analysis report for an analysis session (Req 5.1-5.7).
   *
   * Drives the Agent's report-generation MCP to build the structured content and
   * export PDF/Word files to S3; the returned report exposes `has_pdf`/`has_docx`
   * flags indicating which formats are available for download (Req 5.5).
   */
  generate: (analysisId: string, format?: ReportFormat, sections?: string[]) => {
    const body: GenerateReportRequest = { analysis_id: analysisId };
    if (format) {
      body.format = format;
    }
    if (sections) {
      body.sections = sections;
    }
    return apiClient.post<ReportResponse>('/reports/generate', body);
  },

  /** Resolve a presigned download URL for the exported report file (Req 5.5). */
  getDownloadUrl: (reportId: string, format: ReportFormat) =>
    apiClient.get<ReportDownloadResponse>(
      `/reports/${reportId}/download?format=${encodeURIComponent(format)}`,
    ),
};
