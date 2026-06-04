/**
 * Literature module TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/literature.py` for the
 * Agent-driven literature module: search (CNKI / PubMed / both), detail,
 * bilingual abstract translation, MeSH term suggestion, and literature
 * collection CRUD (collections, folders, saved items) — Req 10.1-10.46.
 *
 * Note on source identifiers: requests use lowercase identifiers
 * ("cnki" / "pubmed"); responses carry canonical uppercase labels
 * ("CNKI" / "PubMed", `SOURCE_LABELS`).
 */

/** Default page size for search results (Req 10.5). */
export const DEFAULT_PAGE_SIZE = 20;

/** Lowercase data-source identifier used in requests (Req 10.6). */
export type DataSourceId = 'cnki' | 'pubmed';

/** Canonical data-source label surfaced in responses (Req 10.22). */
export type DataSourceLabel = 'CNKI' | 'PubMed';

/** All selectable data-source identifiers, defaulting to both (Req 10.7). */
export const DATA_SOURCE_IDS: DataSourceId[] = ['cnki', 'pubmed'];

/** Map a lowercase identifier to its canonical response label. */
export const SOURCE_LABELS: Record<DataSourceId, DataSourceLabel> = {
  cnki: 'CNKI',
  pubmed: 'PubMed',
};

/** Sort key for the merged result list (Req 10.24). */
export type SortBy = 'relevance' | 'date' | 'citations';

// --- Search / detail -------------------------------------------------------

/**
 * A single literature record returned by search / detail.
 *
 * Mirrors `LiteratureRecord`. `abstract_preview` is the first 200 characters of
 * the abstract for list display (Req 10.22); `data_source` is a canonical label
 * ("CNKI" / "PubMed"); `external_id` is the PMID for PubMed.
 */
export interface LiteratureRecord {
  title: string;
  authors: string[];
  journal?: string | null;
  publication_date?: string | null;
  abstract?: string | null;
  abstract_preview?: string | null;
  keywords: string[];
  doi?: string | null;
  data_source: string;
  external_id?: string | null;
  citation_count?: number | null;
}

/** Request body for `POST /literature/search`. */
export interface SearchRequest {
  keywords: string;
  author?: string;
  journal?: string;
  date_from?: string;
  date_to?: string;
  subject?: string;
  sources: DataSourceId[];
  page: number;
  page_size: number;
  sort_by?: SortBy;
}

/**
 * Response from `POST /literature/search`.
 *
 * `total` is the merged result count; `totals` is the per-source count keyed by
 * data-source label ("CNKI" / "PubMed", Req 10.28).
 */
export interface SearchResponse {
  results: LiteratureRecord[];
  page: number;
  page_size: number;
  total: number;
  totals: Record<string, number>;
}

// --- Translation (bilingual) ----------------------------------------------

/** Request body for `POST /literature/{id}/translate`. */
export interface TranslateRequest {
  title?: string;
  abstract?: string;
  source?: string;
  source_language?: 'zh' | 'en';
}

/** Bilingual title/abstract content for the Bilingual_View (Req 10.30-10.34). */
export interface BilingualContent {
  original_title?: string | null;
  translated_title?: string | null;
  original_abstract?: string | null;
  translated_abstract?: string | null;
  source_language: 'zh' | 'en';
  target_language: 'zh' | 'en';
}

// --- MeSH suggestion -------------------------------------------------------

/** Response from `GET /literature/mesh/suggest`. */
export interface MeshSuggestResponse {
  terms: string[];
}

// --- Collections -----------------------------------------------------------

/** A custom folder under a collection (Req 10.39). */
export interface Folder {
  id: string;
  collection_id: string;
  name: string;
  created_at: string;
}

/**
 * A saved literature item (Req 10.37, 10.38).
 *
 * `authors` is a "; "-joined string (the storage column is a single text
 * field); `source` is the data-source label.
 */
export interface CollectedLiterature {
  id: string;
  collection_id: string;
  folder_id?: string | null;
  title: string;
  authors: string;
  journal?: string | null;
  publication_date?: string | null;
  abstract?: string | null;
  doi?: string | null;
  source: string;
  external_id?: string | null;
  created_at: string;
}

/** A literature collection with its folders and saved items. */
export interface Collection {
  id: string;
  name: string;
  created_at: string;
  folders: Folder[];
  items: CollectedLiterature[];
}

/** Response from `GET /literature/collections`. */
export interface CollectionListResponse {
  collections: Collection[];
  total: number;
}

/** Request body for `POST /literature/collections`. */
export interface CreateCollectionRequest {
  name: string;
}

/** Request body for `POST /literature/collections/folders`. */
export interface CreateFolderRequest {
  collection_id: string;
  name: string;
}

/**
 * Request body for `POST /literature/collections/{id}/items`.
 *
 * `authors` accepts either an array of names or a pre-joined string; the
 * backend coerces an array into a "; "-joined string. `source` is the
 * data-source label ("CNKI" / "PubMed" or "cnki" / "pubmed").
 */
export interface SaveLiteratureRequest {
  title: string;
  authors?: string | string[];
  journal?: string | null;
  publication_date?: string | null;
  abstract?: string | null;
  doi?: string | null;
  source: string;
  external_id?: string | null;
  folder_id?: string | null;
}
