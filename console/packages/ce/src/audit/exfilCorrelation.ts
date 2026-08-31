import type { AuditEvent } from './types';

/** Matches Splunk RAG-Exfil-HighConfidence hour bin (`bin _time span=1h`). */
export const EXFIL_HOUR_SECONDS = 3600;

export type ExfilPair = {
  subject: string;
  tenantId: string;
  extractionCount: number;
  canaryCount: number;
  firstTs: number;
  lastTs: number;
  /** True when at least one extraction and one canary share the same UTC hour bucket. */
  sameHour: boolean;
};

function hourBucket(ts: number): number {
  return Math.floor(ts / EXFIL_HOUR_SECONDS) * EXFIL_HOUR_SECONDS;
}

function subjectKey(subject: string, tenantId: string) {
  return `${tenantId}\0${subject}`;
}

/**
 * Subjects that fired both `extraction_suspected` and `canary_triggered`
 * in the provided event set (typically one stats-range window).
 * Aligns with SIEM `RAG-Exfil-HighConfidence` when `sameHour` is true.
 */
export function correlateExfilPairs(events: AuditEvent[]): ExfilPair[] {
  const byKey = new Map<
    string,
    {
      subject: string;
      tenantId: string;
      extractionTs: number[];
      canaryTs: number[];
    }
  >();

  for (const event of events) {
    const kind = String(event.kind || '');
    if (kind !== 'extraction_suspected' && kind !== 'canary_triggered') continue;
    const subject = String(event.subject || '').trim();
    if (!subject) continue;
    const tenantId = String((event as AuditEvent & { tenant_id?: string }).tenant_id || 'default');
    const ts = Number(event.timestamp);
    if (!Number.isFinite(ts)) continue;
    const key = subjectKey(subject, tenantId);
    let row = byKey.get(key);
    if (!row) {
      row = { subject, tenantId, extractionTs: [], canaryTs: [] };
      byKey.set(key, row);
    }
    if (kind === 'extraction_suspected') row.extractionTs.push(ts);
    else row.canaryTs.push(ts);
  }

  const pairs: ExfilPair[] = [];
  for (const row of byKey.values()) {
    if (!row.extractionTs.length || !row.canaryTs.length) continue;
    const extractionBuckets = new Set(row.extractionTs.map(hourBucket));
    const sameHour = row.canaryTs.some((ts) => extractionBuckets.has(hourBucket(ts)));
    const allTs = [...row.extractionTs, ...row.canaryTs];
    pairs.push({
      subject: row.subject,
      tenantId: row.tenantId,
      extractionCount: row.extractionTs.length,
      canaryCount: row.canaryTs.length,
      firstTs: Math.min(...allTs),
      lastTs: Math.max(...allTs),
      sameHour,
    });
  }

  return pairs.sort((a, b) => b.lastTs - a.lastTs || a.subject.localeCompare(b.subject));
}
