import { formatRetrievalTraceSummary } from '../retrieval/trace';
import type { AuditDebug, AuditEvent, AuditFinding } from './types';

export function fmtCount(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? '');
  return n.toLocaleString();
}

export function fmtTs(value?: number) {
  if (!Number.isFinite(value)) return '';
  return new Date((value as number) * 1000).toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** Two-decimal risk for table/drawer cells (avoids 0.799999999 from binary floats). */
export function formatRiskScore(value?: number | null) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '';
  const raw = String(value);
  const frac = raw.includes('.') ? raw.split('.')[1] : '';
  if (frac.length > 2) {
    return (Math.floor(value * 100) / 100).toFixed(2);
  }
  return raw;
}

export function decisionClass(decision?: string) {
  if (decision === 'allow') return 'ok';
  if (decision === 'block') return 'bad';
  return 'warn';
}

const AUDIT_KIND_LABELS: Record<string, string> = {
  ingest_completed: 'Ingest completed',
  challenge_approved: 'Review approved',
  challenge_rejected: 'Review rejected',
  scan_input: 'Input scan',
  scan_output: 'Answer scan',
  query_completed: 'Question completed',
  citation_failed: 'Citation failed',
  tool_invoke: 'Tool call',
  tool_challenge_approved: 'Tool review approved',
  tool_challenge_denied: 'Tool review denied',
  extraction_suspected: 'Suspected scrape',
  canary_triggered: 'Canary hit',
  retrieval_trace: 'Document retrieval',
  permission_drift: 'Permission drift',
  connector_sync: 'Connector sync',
  acl_sync: 'Access update',
  llm_routed: 'Answer model',
  query_trace: 'LLM answer',
  citation_check: 'Citation check',
};

const SCANNER_LABELS: Record<string, string> = {
  pii_ner: 'Names and addresses',
  custom_pattern: 'Custom pattern',
  prompt_injection: 'Prompt injection',
  pii: 'Emails, phones, SSN, SIN, cards',
  tool_policy: 'Tool policy',
  canary: 'Canary',
};

const FINDING_CATEGORY_LABELS: Record<string, string> = {
  ssn: 'SSN',
  sin: 'SIN',
  sample_us_ssn: 'SSN',
  sample_ca_sin: 'SIN',
  person_name: 'Name',
  credit_card: 'Card',
  email: 'Email',
  phone: 'Phone',
  address: 'Address',
};

function titleCaseKey(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function auditKindLabel(kind?: string) {
  if (!kind) return '';
  return AUDIT_KIND_LABELS[kind] ?? titleCaseKey(kind);
}

export function scannerLabel(name?: string) {
  if (!name) return '';
  return SCANNER_LABELS[name] ?? titleCaseKey(name);
}

export function findingCategoryLabel(category?: string) {
  if (!category) return '';
  return FINDING_CATEGORY_LABELS[category] ?? category;
}

export function decisionLabel(decision?: string) {
  if (decision === 'allow') return 'Allowed';
  if (decision === 'challenge') return 'Challenged';
  if (decision === 'block') return 'Blocked';
  if (!decision) return '';
  return titleCaseKey(decision);
}

export const AUDIT_WHERE_FILTERS = [
  { id: 'query', label: 'Query' },
  { id: 'document', label: 'Retrieved document' },
  { id: 'ingest', label: 'Ingest' },
  { id: 'tool', label: 'Tool' },
  { id: 'output', label: 'Answer' },
] as const;

export type AuditWhereFilter = (typeof AUDIT_WHERE_FILTERS)[number]['id'];

const AUDIT_WHERE_LABELS: Record<string, string> = {
  query: 'Query',
  document: 'Retrieved document',
  ingest: 'Ingest',
  tool: 'Tool',
  scan_api: 'Scan API',
  output: 'Answer',
  knowledge_base: 'Knowledge base',
};

export function auditWhereId(source?: string): string {
  const value = String(source || '');
  if (!value) return '';
  if (value === 'rag:user_query' || value.startsWith('rag:user_query:') || value === 'rag:query') {
    return 'query';
  }
  if (value.startsWith('rag:chunk:')) return 'document';
  if (value.startsWith('rag:ingest:')) return 'ingest';
  if (value.startsWith('tool:')) return 'tool';
  if (value.startsWith('rag:scan:')) return 'scan_api';
  if (value === 'rag:output' || value.startsWith('rag:output:') || value === 'rag:llm_routing') {
    return 'output';
  }
  if (value === 'retrieval.explain' || value.startsWith('retrieval.')) return 'knowledge_base';
  return '';
}

export function auditWhereLabel(source?: string) {
  const id = auditWhereId(source);
  return id ? AUDIT_WHERE_LABELS[id] || '' : '';
}

export function formatFindingSummary(findings?: AuditFinding[]) {
  const items = (findings || [])
    .map((finding) => {
      if (!finding) return '';
      const category = findingCategoryLabel(finding.category || '') || '';
      const label = finding.label || '';
      if (category && label && label.toUpperCase() !== category.toUpperCase()) {
        return `${category} (${label})`;
      }
      return category || label;
    })
    .filter(Boolean);
  if (!items.length) return '';
  return [...new Set(items)].join(', ');
}

export function humanizeFindingTokens(detail?: string) {
  return String(detail || '').replace(/\b[a-z][a-z0-9_]*\b/g, (token) => {
    return FINDING_CATEGORY_LABELS[token] || token;
  });
}

export function formatOutputScanDetail(detail?: string) {
  const value = humanizeFindingTokens(String(detail || '').trim());
  if (!value) return 'Answer scan';
  if (value.toLowerCase().startsWith('output scan:')) {
    const rest = value.slice(value.indexOf(':') + 1).trim() || 'clean';
    return rest === 'clean' ? 'Answer scan: clean' : `Answer scan: ${rest}`;
  }
  return value;
}

export function formatAuditEventDetail(kind?: string, detail?: string) {
  if (kind === 'retrieval_trace') {
    return formatRetrievalTraceSummary(detail) || 'Document retrieval';
  }
  if (kind === 'scan_output') {
    return formatOutputScanDetail(detail);
  }
  if (kind === 'scan_input') {
    return humanizeFindingTokens(detail || '');
  }
  return detail || '';
}

export function auditDetailClickHint(kind?: string): { label: string; rest: string } | null {
  if (kind === 'retrieval_trace') {
    return { label: 'click Detail', rest: ' for the full trace' };
  }
  if (kind === 'scan_output' || kind === 'query_trace') {
    return { label: 'click Detail', rest: ' for the LLM answer' };
  }
  return null;
}

export function hasAuditDebug(row?: AuditEvent) {
  const debug = row?.debug;
  if (!debug || typeof debug !== 'object') return false;
  return Boolean(
    debug.query_preview ||
      debug.input_preview ||
      debug.output_preview ||
      (Array.isArray(debug.citation_claims) && debug.citation_claims.length),
  );
}

export function queryTraceMatches(
  row?: AuditEvent,
  match?: { sinceTs?: number; subject?: string },
) {
  if (!row || row.kind !== 'query_trace' || !hasAuditDebug(row)) return false;
  if (!match) return true;
  const ts = Number(row.timestamp) || 0;
  if (match.sinceTs != null && ts < Number(match.sinceTs)) return false;
  if (match.subject && String(row.subject || '') !== String(match.subject)) return false;
  return true;
}

export function findLatestQueryTraceIndex(
  rows: AuditEvent[],
  match?: { sinceTs?: number; subject?: string },
) {
  if (!Array.isArray(rows) || !rows.length) return -1;
  let best = -1;
  let bestTs = -Infinity;
  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index];
    if (!queryTraceMatches(row, match)) continue;
    const ts = Number(row.timestamp) || 0;
    if (ts >= bestTs) {
      bestTs = ts;
      best = index;
    }
  }
  return best;
}

export function auditEventPin(row?: AuditEvent) {
  if (!row) return '';
  return `${row.timestamp}|${row.kind}|${row.detail || ''}|${row.subject || ''}`;
}

export function chartBucketSeconds(bucket: string) {
  if (bucket === '5m') return 300;
  if (bucket === '1d') return 86400;
  return 3600;
}

export const AUDIT_CHART_COL_WIDTH = 14;
export const AUDIT_CHART_COL_GAP = 4;
export const AUDIT_CHART_COL_WIDTH_MAX = 48;

export function plotWidth(bucketCount: number, colWidth: number, gap = AUDIT_CHART_COL_GAP) {
  return bucketCount * colWidth + Math.max(0, bucketCount - 1) * gap;
}

/** Expand columns to fill the viewport when there is room; otherwise keep dense scrollable bars. */
export function columnWidth(
  bucketCount: number,
  viewport: number,
  {
    minWidth = AUDIT_CHART_COL_WIDTH,
    maxWidth = AUDIT_CHART_COL_WIDTH_MAX,
    gap = AUDIT_CHART_COL_GAP,
  }: { minWidth?: number; maxWidth?: number; gap?: number } = {},
) {
  if (bucketCount <= 0) return minWidth;
  if (viewport <= 0) return minWidth;
  const minPlotWidth = plotWidth(bucketCount, minWidth, gap);
  if (minPlotWidth >= viewport) return minWidth;
  const usable = viewport - Math.max(0, bucketCount - 1) * gap;
  const expanded = Math.floor(usable / bucketCount);
  return Math.max(minWidth, Math.min(maxWidth, expanded));
}

export function computeBarScale(maxValue: number) {
  const dataMax = Math.max(Number(maxValue) || 0, 0);
  let scaleMax = 10;
  if (dataMax <= 10) scaleMax = 10;
  else if (dataMax <= 50) scaleMax = Math.ceil(dataMax / 10) * 10;
  else if (dataMax <= 200) scaleMax = Math.ceil(dataMax / 20) * 20;
  else scaleMax = Math.ceil(dataMax / 50) * 50;

  let step = 10;
  if (scaleMax <= 10) step = 2;
  else if (scaleMax <= 50) step = 10;
  else if (scaleMax <= 100) step = 20;
  else step = Math.max(10, Math.ceil(scaleMax / 5 / 10) * 10);

  const ticks: number[] = [];
  for (let value = 0; value <= scaleMax; value += step) ticks.push(value);
  if (ticks[ticks.length - 1] !== scaleMax) ticks.push(scaleMax);
  return { scaleMax, ticks };
}

export function trimAuditChartSeries<T extends { total?: number; allow?: number; challenge?: number; block?: number }>(
  series: T[],
) {
  if (!Array.isArray(series) || series.length <= 1) return series || [];
  const totalAt = (entry: T) =>
    entry.total ?? ((entry.allow || 0) + (entry.challenge || 0) + (entry.block || 0));
  let start = 0;
  let end = series.length - 1;
  while (start < end && totalAt(series[start]) === 0) start += 1;
  while (end > start && totalAt(series[end]) === 0) end -= 1;
  return series.slice(start, end + 1);
}

export function isSameLocalDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function fmtRelativeDay(d: Date, now = new Date()) {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startOfDay.getTime() - startOfToday.getTime()) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === -1) return 'Yesterday';
  return null;
}

export function fmtChartBucketLabel(
  bucketStart: number | undefined,
  bucket: string,
  context: { prevDay?: Date | null; isFirst?: boolean },
) {
  const start = Number(bucketStart);
  if (!Number.isFinite(start)) return { line1: '', line2: '' };
  const d = new Date(start * 1000);
  const now = new Date();
  const rel = fmtRelativeDay(d, now);
  const time = d.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: bucket === '5m' ? '2-digit' : undefined,
  });

  if (bucket === '1d') {
    if (rel === 'Today') return { line1: 'Today', line2: '' };
    if (rel === 'Yesterday') return { line1: 'Yesterday', line2: '' };
    return {
      line1: d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
      line2: '',
    };
  }

  // 5m / 1h: show the date only on the first tick and when the local day changes.
  const dateLine = rel || d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  const prev = context.prevDay;
  const showDate = context.isFirst || (prev && !isSameLocalDay(d, prev));
  if (showDate) return { line1: dateLine, line2: time };
  return { line1: time, line2: '' };
}

/** Prefer ~72px per tick label so two-line date/time ticks do not collide. */
export function chartTickBudget(plotWidthPx: number, minTicks = 3, maxTicks = 12) {
  if (!Number.isFinite(plotWidthPx) || plotWidthPx <= 0) return minTicks;
  return Math.max(minTicks, Math.min(maxTicks, Math.floor(plotWidthPx / 72)));
}

export function pickChartTickIndexes(count: number, maxTicks = 7) {
  if (count <= 0) return [];
  if (count === 1) return [0];
  const budget = Math.max(2, Math.floor(maxTicks));
  if (count <= budget) return Array.from({ length: count }, (_, index) => index);
  const picked: number[] = [];
  for (let i = 0; i < budget; i++) {
    picked.push(Math.round((i * (count - 1)) / (budget - 1)));
  }
  return [...new Set(picked)];
}

export function fmtChartBucketRange(bucketStart: number, bucket: string) {
  const start = Number(bucketStart);
  if (!Number.isFinite(start)) return '';
  const end = start + chartBucketSeconds(bucket);
  const d0 = new Date(start * 1000);
  const d1 = new Date(end * 1000);
  if (bucket === '1d') {
    return d0.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  }
  const datePart = d0.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  const t0 = d0.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  const t1 = d1.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return isSameLocalDay(d0, d1) ? `${datePart}, ${t0} – ${t1}` : `${fmtTs(start)} – ${fmtTs(end)}`;
}

export function fmtChartColTitle(
  entry: { bucket_start?: number; allow?: number; challenge?: number; block?: number },
  bucket: string,
) {
  const allow = entry.allow || 0;
  const challenge = entry.challenge || 0;
  const block = entry.block || 0;
  const total = allow + challenge + block;
  const range = fmtChartBucketRange(Number(entry.bucket_start), bucket);
  const parts: string[] = [];
  if (allow) parts.push(`${fmtCount(allow)} allowed`);
  if (challenge) parts.push(`${fmtCount(challenge)} challenged`);
  if (block) parts.push(`${fmtCount(block)} blocked`);
  const breakdown = parts.length ? ` (${parts.join(', ')})` : '';
  return `${range}: ${fmtCount(total)} events${breakdown}`;
}

export function isIngestAuditSource(source?: string, kind?: string): boolean {
  if (kind === 'ingest_completed') return true;
  return Boolean(source && String(source).startsWith('rag:ingest:'));
}

export function renderDebugHint(kind?: string, source?: string) {
  const label = kind ? String(kind) : 'this event';
  if (isIngestAuditSource(source, kind)) {
    return `No debug previews on ${label}. Re-ingest with audit_debug checked in Documents & Ingest, or set audit.debug_mode: true in policy for a tuning window.`;
  }
  return `No debug previews on ${label}. Re-run the query in Query Lab with audit_debug checked, or set audit.debug_mode: true in policy for a tuning window.`;
}

export function hasDebugContent(debug?: AuditDebug) {
  return Boolean(
    debug?.query_preview ||
      debug?.input_preview ||
      debug?.output_preview ||
      (Array.isArray(debug?.citation_claims) && debug.citation_claims.length),
  );
}
