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
/** All selectable data-source identifiers, defaulting to both (Req 10.7). */
export const DATA_SOURCE_IDS = ['cnki', 'pubmed'];
/** Map a lowercase identifier to its canonical response label. */
export const SOURCE_LABELS = {
    cnki: 'CNKI',
    pubmed: 'PubMed',
};
