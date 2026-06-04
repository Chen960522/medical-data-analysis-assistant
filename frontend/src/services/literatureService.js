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
/** Build the query string for an optional set of params (drops empties). */
function buildQuery(params) {
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
    search: (body, signal) => apiClient.post('/literature/search', body, { signal }),
    /**
     * Get the full detail of a literature record (Req 10.26).
     *
     * `literatureId` is the external id (PMID for PubMed); `source` is required.
     */
    getDetail: (literatureId, source, signal) => apiClient.get(`/literature/${encodeURIComponent(literatureId)}${buildQuery({ source })}`, { signal }),
    /**
     * Translate a record's title + abstract for the bilingual view (Req 10.29-10.35).
     *
     * Since search results are ephemeral the content is supplied in the body.
     */
    translate: (literatureId, body, signal) => apiClient.post(`/literature/${encodeURIComponent(literatureId)}/translate`, body, { signal }),
    /** Suggest relevant MeSH terms for a query as the user types (Req 10.20). */
    suggestMesh: (q, signal) => apiClient.get(`/literature/mesh/suggest${buildQuery({ q })}`, { signal }),
    /** Create a literature collection (Req 10.36). */
    createCollection: (body) => apiClient.post('/literature/collections', body),
    /**
     * List the user's collections, newest first (Req 10.38).
     *
     * Optionally filters saved items by data source (Req 10.40) and/or a
     * title/keyword search term (Req 10.42).
     */
    listCollections: (options) => apiClient.get(`/literature/collections${buildQuery({ source: options?.source, q: options?.q })}`),
    /** Delete a collection and its folders/items (Req 10.41). */
    deleteCollection: (collectionId) => apiClient.delete(`/literature/collections/${collectionId}`),
    /** Create a custom folder under a collection (Req 10.39). */
    createFolder: (body) => apiClient.post('/literature/collections/folders', body),
    /** Save a literature record into a collection (Req 10.36, 10.37). */
    saveItem: (collectionId, body) => apiClient.post(`/literature/collections/${collectionId}/items`, body),
    /** Remove a saved literature item from a collection (Req 10.41). */
    removeItem: (collectionId, itemId) => apiClient.delete(`/literature/collections/${collectionId}/items/${itemId}`),
};
