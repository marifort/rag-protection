export type RetrievalDecision = {
  chunk_id?: string;
  document_id?: string;
  title?: string;
  score?: number;
  outcome?: string;
  detail?: string;
};

export type RetrievalTraceSummary = {
  candidates: number;
  selected: number;
  excluded_acl: number;
  excluded_quarantine: number;
  excluded_low_score: number;
  not_in_top_k: number;
  other: number;
};

const OUTCOME_ORDER: Record<string, number> = {
  excluded_quarantine: 0,
  excluded_acl: 1,
  excluded_low_score: 2,
  not_in_top_k: 3,
  selected: 4,
};

export function outcomeClass(outcome?: string) {
  if (outcome === 'selected') return 'ok';
  if (outcome === 'excluded_acl' || outcome === 'excluded_quarantine') return 'bad';
  if (outcome === 'excluded_low_score' || outcome === 'not_in_top_k') return 'warn';
  return '';
}

export function outcomeLabel(outcome?: string) {
  switch (outcome) {
    case 'selected':
      return 'Used';
    case 'excluded_acl':
      return 'Access denied';
    case 'excluded_quarantine':
      return 'Held for review';
    case 'excluded_low_score':
      return 'Below score';
    case 'not_in_top_k':
      return 'Not in top results';
    default:
      return outcome || '—';
  }
}

export function retrievalReasonLabel(detail?: string) {
  const value = String(detail || '').trim();
  if (!value) return '—';
  if (value === 'no token overlap with query') return 'No words in common with the question';
  if (value === 'metadata.status=quarantined') return 'Document is held for review';
  if (value === 'trace unavailable for store backend') return 'Trace not available for this store';
  const groups = value.match(/^required groups (.+)$/);
  if (groups) return `Needs access: ${groups[1]}`;
  const topBy = value.match(/^top_(\d+) by (?:vector )?score$/);
  if (topBy) return `Ranked in the top ${topBy[1]}`;
  const below = value.match(/^ranked below top_(\d+)$/);
  if (below) return `Ranked below the top ${below[1]}`;
  return value;
}

export function formatRetrievalTraceSummary(detail?: string) {
  const parsed = parseRetrievalTraceDetail(detail);
  if (!parsed) return '';
  const counts = summarizeTrace(parsed.trace);
  const candidates = parsed.candidates ?? counts.candidates;
  const selected = parsed.selected ?? counts.selected;
  const parts = [`${selected} used of ${candidates} considered`];
  if (counts.excluded_acl) parts.push(`${counts.excluded_acl} access denied`);
  if (counts.excluded_quarantine) parts.push(`${counts.excluded_quarantine} held for review`);
  if (counts.excluded_low_score) parts.push(`${counts.excluded_low_score} below score`);
  if (counts.not_in_top_k) parts.push(`${counts.not_in_top_k} not in top results`);
  if (counts.other) parts.push(`${counts.other} other`);
  return parts.join(' · ');
}

export function summarizeTrace(rows: RetrievalDecision[]): RetrievalTraceSummary {
  const summary: RetrievalTraceSummary = {
    candidates: rows.length,
    selected: 0,
    excluded_acl: 0,
    excluded_quarantine: 0,
    excluded_low_score: 0,
    not_in_top_k: 0,
    other: 0,
  };
  for (const row of rows) {
    const outcome = row.outcome || '';
    if (outcome === 'selected') summary.selected += 1;
    else if (outcome === 'excluded_acl') summary.excluded_acl += 1;
    else if (outcome === 'excluded_quarantine') summary.excluded_quarantine += 1;
    else if (outcome === 'excluded_low_score') summary.excluded_low_score += 1;
    else if (outcome === 'not_in_top_k') summary.not_in_top_k += 1;
    else summary.other += 1;
  }
  return summary;
}

/** Pipeline narrative order: quarantine → ACL drops → low score → not top-k → selected. */
export function sortRetrievalTrace(rows: RetrievalDecision[]): RetrievalDecision[] {
  return [...rows].sort((a, b) => {
    const ao = OUTCOME_ORDER[a.outcome || ''] ?? 50;
    const bo = OUTCOME_ORDER[b.outcome || ''] ?? 50;
    if (ao !== bo) return ao - bo;
    return (Number(b.score) || 0) - (Number(a.score) || 0);
  });
}

export function parseRetrievalTraceDetail(detail?: string): {
  query_len?: number;
  candidates?: number;
  selected?: number;
  trace: RetrievalDecision[];
} | null {
  if (!detail || typeof detail !== 'string') return null;
  try {
    const parsed = JSON.parse(detail) as {
      query_len?: number;
      candidates?: number;
      selected?: number;
      trace?: RetrievalDecision[];
    };
    if (!parsed || !Array.isArray(parsed.trace)) return null;
    return {
      query_len: parsed.query_len,
      candidates: parsed.candidates,
      selected: parsed.selected,
      trace: parsed.trace,
    };
  } catch {
    return null;
  }
}
