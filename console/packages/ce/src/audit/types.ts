export type AuditFinding = {
  scanner?: string;
  category?: string;
  label?: string;
  severity?: number | string;
  snippet?: string;
  detail?: string;
};

export type AuditDebug = {
  query_preview?: string;
  input_preview?: string;
  output_preview?: string;
  redactions?: number | string;
  chunk_ids?: string[];
  citation_coverage_ratio?: number;
  citation_claims?: Array<{
    sentence?: string;
    chunk_id?: string | null;
    supported?: boolean;
    entailment_score?: number | null;
  }>;
};

export type AuditEvent = {
  timestamp?: number;
  kind?: string;
  decision?: string;
  risk_score?: number;
  subject?: string;
  source?: string;
  detail?: string;
  tenant_id?: string;
  findings?: AuditFinding[];
  debug?: AuditDebug;
};

export type AuditListResponse = {
  events?: AuditEvent[];
  total?: number;
  offset?: number;
  limit?: number;
  filters?: Record<string, string>;
};

export type AuditStatsBucket = {
  bucket_start?: number;
  allow?: number;
  challenge?: number;
  block?: number;
  total?: number;
};

export type AuditStatsResponse = {
  total_events?: number;
  by_decision?: Record<string, number>;
  by_kind?: Record<string, number>;
  by_scanner?: Record<string, number>;
  series?: AuditStatsBucket[];
};

export type AuditDrilldown = {
  from_ts: number;
  to_ts: number;
  label: string;
  decision?: string;
};
