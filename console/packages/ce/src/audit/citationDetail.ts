export type CitationClaimAuditRow = {
  sentence?: string;
  chunk_id?: string | null;
  supported?: boolean;
  entailment_score?: number | null;
  offset_start?: number;
};

export type CitationAuditDetail = {
  summary?: string;
  hard_gate_failed?: boolean;
  unsupported_count?: number;
  coverage_ratio?: number;
  claims: CitationClaimAuditRow[];
  unsupported_claims: CitationClaimAuditRow[];
};

function asClaimRows(value: unknown): CitationClaimAuditRow[] {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is CitationClaimAuditRow => Boolean(row) && typeof row === 'object');
}

/** Parse structured `citation_failed` audit detail JSON (E3.4 / E3.5). */
export function parseCitationAuditDetail(detail?: string): CitationAuditDetail | null {
  if (!detail || typeof detail !== 'string') return null;
  try {
    const parsed = JSON.parse(detail) as {
      summary?: string;
      hard_gate_failed?: boolean;
      unsupported_count?: number;
      coverage_ratio?: number;
      claims?: unknown;
      unsupported_claims?: unknown;
    };
    if (!parsed || typeof parsed !== 'object') return null;
    const claims = asClaimRows(parsed.claims);
    const unsupported = asClaimRows(parsed.unsupported_claims);
    if (
      !claims.length &&
      !unsupported.length &&
      parsed.coverage_ratio == null &&
      parsed.summary == null
    ) {
      return null;
    }
    return {
      summary: parsed.summary,
      hard_gate_failed: parsed.hard_gate_failed,
      unsupported_count: parsed.unsupported_count,
      coverage_ratio: parsed.coverage_ratio,
      claims,
      unsupported_claims: unsupported,
    };
  } catch {
    return null;
  }
}
