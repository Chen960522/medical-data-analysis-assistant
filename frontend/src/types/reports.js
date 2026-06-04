/**
 * Analysis report TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/reports.py` for the
 * Agent-driven report module: generating a structured Analysis_Report for an
 * analysis session and downloading the exported report file (PDF / Word).
 * Supports inline report generation and download from the analysis dashboard
 * (Req 5.5-5.7).
 */
/** Human-readable label for a report format (Req 5.5). */
export const REPORT_FORMAT_LABELS = {
    pdf: 'PDF',
    docx: 'Word',
};
