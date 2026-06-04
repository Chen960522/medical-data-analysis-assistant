/**
 * Analysis report TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/reports.py` for the
 * Agent-driven report module: generating a structured Analysis_Report for an
 * analysis session and downloading the exported report file (PDF / Word).
 * Supports inline report generation and download from the analysis dashboard
 * (Req 5.5-5.7).
 */

/** Exported report format. Only PDF and Word (.docx) are supported (Req 5.5). */
export type ReportFormat = 'pdf' | 'docx';

/** Human-readable label for a report format (Req 5.5). */
export const REPORT_FORMAT_LABELS: Record<ReportFormat, string> = {
  pdf: 'PDF',
  docx: 'Word',
};

/**
 * Request body for `POST /reports/generate` (Req 5.1-5.7).
 *
 * `sections` optionally restricts/orders the report sections (the five required
 * sections are always present regardless). `format` is an optional hint for the
 * export format(s) to produce.
 */
export interface GenerateReportRequest {
  analysis_id: string;
  sections?: string[];
  format?: ReportFormat;
}

/**
 * Response from `POST /reports/generate` (Req 5.1-5.4, 5.7).
 *
 * Exposes the structured report `content` alongside boolean download
 * availability flags so the client knows which formats can be downloaded via
 * the download endpoint (Req 5.5).
 */
export interface ReportResponse {
  id: string;
  session_id: string;
  title: string;
  content: Record<string, unknown>;
  has_pdf: boolean;
  has_docx: boolean;
  created_at: string;
}

/** Response from `GET /reports/{report_id}/download` (Req 5.5). */
export interface ReportDownloadResponse {
  download_url: string;
  format: string;
}
