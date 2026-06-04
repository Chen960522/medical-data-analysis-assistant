/**
 * PDF translation module TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/translation.py` for the
 * Agent-driven PDF literature translation module (Requirement 11): uploading a
 * PDF, triggering full-document translation, querying progress, fetching the
 * bilingual Translation_Result, downloading the exported document, and
 * listing / deleting translation history — Req 11.1-11.50.
 */

/** Document language code. Only Chinese and English are supported (Req 11.17). */
export type LanguageCode = 'zh' | 'en';

/** Source-language selection in the UI; 'auto' lets the Agent detect (Req 11.19). */
export type SourceLanguageChoice = LanguageCode | 'auto';

/** Human-readable label for a language code (Req 11.19, 11.33). */
export const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  zh: '中文',
  en: '英文',
};

/** Resolve a (possibly null) language code to a display label. */
export function languageLabel(code?: LanguageCode | string | null): string {
  if (code === 'zh' || code === 'en') {
    return LANGUAGE_LABELS[code];
  }
  return '未知';
}

/** Download export format (Req 11.38, 11.39). */
export type DownloadFormat = 'pdf' | 'docx';

/** Download content mode: bilingual or translated-only (Req 11.41). */
export type DownloadMode = 'bilingual' | 'translation';

/** Bilingual document view mode (Req 11.35). */
export type DocumentViewMode = 'bilingual' | 'original' | 'translation';

// --- Upload ----------------------------------------------------------------

/**
 * Response from `POST /translation/upload` (Req 11.7).
 *
 * `page_count` is determined later during parsing and may be `null` until the
 * document is translated.
 */
export interface TranslationUploadResponse {
  id: string;
  original_filename: string;
  file_size: number;
  page_count?: number | null;
  status: string;
  created_at: string;
}

// --- Translate -------------------------------------------------------------

/**
 * Request body for `POST /translation/{id}/translate` (Req 11.19, 11.21).
 *
 * `source_language` optionally overrides the auto-detected language; omit it to
 * let the Agent detect the document language.
 */
export interface TranslateRequest {
  source_language?: LanguageCode;
}

/** Response from `GET /translation/{id}/status` (Req 11.28). */
export interface TranslationStatusResponse {
  id: string;
  status: string;
  /** 0-100 progress percentage. */
  progress?: number | null;
  source_language?: LanguageCode | null;
  target_language?: LanguageCode | null;
}

/**
 * The bilingual Translation_Result (Req 11.24, 11.30-11.34).
 *
 * `original_paragraphs` and `translated_paragraphs` are index-aligned: row `i`
 * of each array forms one original/translated pair.
 */
export interface TranslationResultResponse {
  id: string;
  translation_id: string;
  source_language?: LanguageCode | null;
  target_language?: LanguageCode | null;
  status: string;
  original_paragraphs: string[];
  translated_paragraphs: string[];
  document_structure?: unknown;
}

// --- Download --------------------------------------------------------------

/** Response from `GET /translation/{id}/download` (Req 11.37-11.41). */
export interface TranslationDownloadResponse {
  download_url: string;
  format: string;
  mode: string;
}

// --- History ---------------------------------------------------------------

/** A single translation-history entry (Req 11.43, 11.44). */
export interface TranslationHistoryItem {
  id: string;
  original_filename: string;
  file_size: number;
  page_count?: number | null;
  source_language?: LanguageCode | null;
  target_language?: LanguageCode | null;
  status: string;
  created_at: string;
  completed_at?: string | null;
}

/** Response from `GET /translation/history`. */
export interface TranslationHistoryResponse {
  records: TranslationHistoryItem[];
  total: number;
}
