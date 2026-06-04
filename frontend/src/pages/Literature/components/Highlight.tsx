/**
 * Keyword highlighting helper.
 *
 * Wraps occurrences of the matched search terms within displayed text in a
 * `<mark>`-style span so users can see why a result matched (Req 10.23).
 *
 * Matching is case-insensitive; the query is split on whitespace into terms and
 * each term is regex-escaped so special characters are matched literally.
 * Overlapping/duplicate terms are de-duplicated and longer terms are matched
 * first to avoid partial-match fragmentation.
 */

import { Fragment, type ReactNode } from 'react';

import { PALETTE } from '../../../theme/tokens';

export interface HighlightProps {
  /** The text to render with matched terms highlighted. */
  text?: string | null;
  /** The raw search query (split on whitespace) or an explicit list of terms. */
  terms?: string | string[];
}

/** Escape regex special characters so a term matches literally. */
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Split a query into distinct, non-empty terms (longest first). */
function normalizeTerms(terms?: string | string[]): string[] {
  const raw = Array.isArray(terms) ? terms : (terms ?? '').split(/\s+/);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const term of raw) {
    const trimmed = term.trim();
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(trimmed);
  }
  // Longer terms first so e.g. "heart failure" wins over "heart".
  return result.sort((a, b) => b.length - a.length);
}

const MARK_STYLE: React.CSSProperties = {
  backgroundColor: PALETTE.warning,
  color: PALETTE.neutral.black,
  padding: '0 1px',
  borderRadius: 2,
};

export function Highlight({ text, terms }: HighlightProps) {
  const content = text ?? '';
  const normalized = normalizeTerms(terms);

  if (!content || normalized.length === 0) {
    return <>{content}</>;
  }

  const pattern = new RegExp(`(${normalized.map(escapeRegExp).join('|')})`, 'gi');
  const parts = content.split(pattern);

  const nodes: ReactNode[] = parts.map((part, index) => {
    // Odd indices are the captured matches.
    if (index % 2 === 1) {
      return (
        <mark key={index} style={MARK_STYLE}>
          {part}
        </mark>
      );
    }
    return <Fragment key={index}>{part}</Fragment>;
  });

  return <>{nodes}</>;
}

export default Highlight;
