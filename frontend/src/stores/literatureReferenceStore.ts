/**
 * Literature methodology reference store.
 *
 * Carries a pending literature reference from the Literature_Search_Module to
 * the Chat_Interface on the analysis page (Req 10.44, 10.45). When the User
 * chooses to "引用方法学" (reference a literature methodology) from a
 * Literature_Record detail, the record's title, abstract, and data source are
 * staged here and the User is navigated to the analysis page, where the Chat
 * panel seeds the composer with the literature context so the User can ask the
 * AI_Analyzer to apply a similar analytical approach to the current dataset.
 */

import { create } from 'zustand';

import type { LiteratureRecord } from '../types/literature';

/** A staged literature reference awaiting consumption by the Chat panel. */
export interface LiteratureReference {
  title: string;
  abstract?: string | null;
  dataSource: string;
}

interface LiteratureReferenceState {
  /** The pending reference, or null when none is staged. */
  pending: LiteratureReference | null;
  /** Stage a literature reference for the Chat panel to pick up. */
  setReference: (record: Pick<LiteratureRecord, 'title' | 'abstract' | 'data_source'>) => void;
  /** Consume (read + clear) the pending reference; returns it or null. */
  consumeReference: () => LiteratureReference | null;
  /** Clear any pending reference without consuming it. */
  clearReference: () => void;
}

/**
 * Build the seed message the Chat composer is pre-filled with so the User can
 * ask the AI to apply a similar methodology to their dataset (Req 10.45).
 */
export function buildReferencePrompt(reference: LiteratureReference): string {
  const lines = [
    `参考文献方法学（来源：${reference.dataSource}）：`,
    `标题：${reference.title}`,
  ];
  if (reference.abstract && reference.abstract.trim().length > 0) {
    lines.push(`摘要：${reference.abstract.trim()}`);
  }
  lines.push('');
  lines.push('请参考上述文献的分析方法，对当前数据集应用类似的分析思路。');
  return lines.join('\n');
}

export const useLiteratureReferenceStore = create<LiteratureReferenceState>((set, get) => ({
  pending: null,

  setReference: (record) =>
    set({
      pending: {
        title: record.title,
        abstract: record.abstract ?? null,
        dataSource: record.data_source,
      },
    }),

  consumeReference: () => {
    const { pending } = get();
    if (pending) {
      set({ pending: null });
    }
    return pending;
  },

  clearReference: () => set({ pending: null }),
}));
