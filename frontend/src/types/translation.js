/**
 * PDF translation module TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/translation.py` for the
 * Agent-driven PDF literature translation module (Requirement 11): uploading a
 * PDF, triggering full-document translation, querying progress, fetching the
 * bilingual Translation_Result, downloading the exported document, and
 * listing / deleting translation history — Req 11.1-11.50.
 */
/** Human-readable label for a language code (Req 11.19, 11.33). */
export const LANGUAGE_LABELS = {
    zh: '中文',
    en: '英文',
};
/** Resolve a (possibly null) language code to a display label. */
export function languageLabel(code) {
    if (code === 'zh' || code === 'en') {
        return LANGUAGE_LABELS[code];
    }
    return '未知';
}
