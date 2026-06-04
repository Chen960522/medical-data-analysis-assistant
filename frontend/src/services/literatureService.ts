/**
 * Literature API service.
 *
 * Wraps the `/literature` endpoints defined in
 * `backend/app/api/v1/literature.py` for the Agent-driven literature module:
 * searching (CNKI / PubMed / both), fetching full detail, bilingual abstract
 * translation, MeSH term suggestion, and literature-collection CRUD
 * (collections, folders, saved items) — Req 10.1-10.46.
 *
 * Search results are ephemeral (produced live by the Agent and not persisted),
 * so detail/translate operations pass the record's identifying fields rather
 * than relying on a stored id.
 */

import { apiClient } from './apiClient';
import type {
  BilingualContent,
  Collection,
  CollectionListResponse,
  CreateCollectionRequest,
  CreateFolderRequest,
  DataSourceId,
  Folder,
  CollectedLiterature,
  LiteratureRecord,
  MeshSuggestResponse,
  SaveLiteratureRequest,
  SearchRequest,
  SearchResponse,
  TranslateRequest,
} from '../types/literature';

/** Build the query string for an optional set of params (drops empties). */
function buildQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, value);
    }
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const literatureService = {
  /** Search literature across the selected data sources (Req 10.2-10.8, 10.24, 10.28). */
  search: (body: SearchRequest, signal?: AbortSignal) =>
    apiClient.post<SearchResponse>('/literature/search', body, { signal }),

  /**
   * Get the full detail of a literature record (Req 10.26).
   *
   * `literatureId` is the external id (PMID for PubMed); `source` is required.
   */
  getDetail: (literatureId: string, source: DataSourceId, signal?: AbortSignal) =>
    apiClient.get<LiteratureRecord>(
      `/literature/${encodeURIComponent(literatureId)}${buildQuery({ source })}`,
      { signal },
    ),

  /**
   * Translate a record's title + abstract for the bilingual view (Req 10.29-10.35).
   *
   * Since search results are ephemeral the content is supplied in the body.
   */
  translate: (literatureId: string, body: TranslateRequest, signal?: AbortSignal) =>
    apiClient.post<BilingualContent>(
      `/literature/${encodeURIComponent(literatureId)}/translate`,
      body,
      { signal },
    ),

  /** Suggest relevant MeSH terms for a query as the user types (Req 10.20). */
  suggestMesh: (q: string, signal?: AbortSignal) =>
    apiClient.get<MeshSuggestResponse>(`/literature/mesh/suggest${buildQuery({ q })}`, { signal }),

  /** Create a literature collection (Req 10.36). */
  createCollection: (body: CreateCollectionRequest) =>
    apiClient.post<Collection>('/literature/collections', body),

  /**
   * List the user's collections, newest first (Req 10.38).
   *
   * Optionally filters saved items by data source (Req 10.40) and/or a
   * title/keyword search term (Req 10.42).
   */
  listCollections: (options?: { source?: DataSourceId; q?: string }) =>
    apiClient.get<CollectionListResponse>(
      `/literature/collections${buildQuery({ source: options?.source, q: options?.q })}`,
    ),

  /** Delete a collection and its folders/items (Req 10.41). */
  deleteCollection: (collectionId: string) =>
    apiClient.delete<void>(`/literature/collections/${collectionId}`),

  /** Create a custom folder under a collection (Req 10.39). */
  createFolder: (body: CreateFolderRequest) =>
    apiClient.post<Folder>('/literature/collections/folders', body),

  /** Save a literature record into a collection (Req 10.36, 10.37). */
  saveItem: (collectionId: string, body: SaveLiteratureRequest) =>
    apiClient.post<CollectedLiterature>(`/literature/collections/${collectionId}/items`, body),

  /** Remove a saved literature item from a collection (Req 10.41). */
  removeItem: (collectionId: string, itemId: string) =>
    apiClient.delete<void>(`/literature/collections/${collectionId}/items/${itemId}`),
};
