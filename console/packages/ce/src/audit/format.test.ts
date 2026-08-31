import { describe, expect, it } from 'vitest';

import {
  auditDetailClickHint,
  auditKindLabel,
  auditWhereLabel,
  chartTickBudget,
  columnWidth,
  decisionLabel,
  findLatestQueryTraceIndex,
  fmtChartBucketLabel,
  formatAuditEventDetail,
  formatOutputScanDetail,
  isIngestAuditSource,
  pickChartTickIndexes,
  plotWidth,
  queryTraceMatches,
  renderDebugHint,
  scannerLabel,
  findingCategoryLabel,
  formatRiskScore,
} from './format';
import type { AuditEvent } from './types';

const TRACE: AuditEvent = {
  timestamp: 100,
  kind: 'query_trace',
  subject: 'employee-1',
  detail: 'query',
  debug: { query_preview: 'hello' },
};

describe('queryTraceMatches', () => {
  it('requires query_trace kind with debug previews', () => {
    expect(queryTraceMatches(TRACE, { sinceTs: 0, subject: 'employee-1' })).toBe(true);
    expect(queryTraceMatches({ ...TRACE, kind: 'query' }, { sinceTs: 0 })).toBe(false);
    expect(queryTraceMatches({ ...TRACE, debug: {} }, { sinceTs: 0 })).toBe(false);
  });

  it('filters by sinceTs and subject when provided', () => {
    expect(queryTraceMatches(TRACE, { sinceTs: 101 })).toBe(false);
    expect(queryTraceMatches(TRACE, { sinceTs: 99, subject: 'employee-1' })).toBe(true);
    expect(queryTraceMatches(TRACE, { sinceTs: 99, subject: 'other' })).toBe(false);
  });
});

describe('renderDebugHint', () => {
  it('points ingest events at Documents & Ingest audit_debug', () => {
    const hint = renderDebugHint('scan_input', 'rag:ingest:doc-custom-778');
    expect(hint).toContain('Documents & Ingest');
    expect(hint).not.toContain('Query Lab');
    expect(isIngestAuditSource('rag:ingest:doc-1', 'scan_input')).toBe(true);
    expect(isIngestAuditSource(undefined, 'ingest_completed')).toBe(true);
  });

  it('keeps Query Lab guidance for non-ingest events', () => {
    const hint = renderDebugHint('scan_input', 'rag:query');
    expect(hint).toContain('Query Lab');
    expect(hint).not.toContain('Documents & Ingest');
    expect(isIngestAuditSource('rag:query', 'scan_input')).toBe(false);
  });
});

describe('findLatestQueryTraceIndex', () => {
  it('returns the newest matching trace row', () => {
    const rows: AuditEvent[] = [
      { ...TRACE, timestamp: 90, subject: 'employee-1' },
      { ...TRACE, timestamp: 110, subject: 'employee-1' },
      { ...TRACE, timestamp: 105, subject: 'employee-2' },
    ];
    expect(findLatestQueryTraceIndex(rows, { sinceTs: 80, subject: 'employee-1' })).toBe(1);
  });

  it('returns -1 when no trace matches', () => {
    expect(findLatestQueryTraceIndex([], { sinceTs: 0 })).toBe(-1);
    expect(findLatestQueryTraceIndex([{ kind: 'query', timestamp: 1 }], { sinceTs: 0 })).toBe(-1);
  });
});

describe('chart x-axis scale helpers', () => {
  it('expands column width to fill the viewport when buckets are sparse', () => {
    expect(columnWidth(4, 400)).toBeGreaterThan(14);
    expect(columnWidth(4, 400)).toBeLessThanOrEqual(48);
    expect(plotWidth(4, columnWidth(4, 400))).toBeLessThanOrEqual(400);
  });

  it('keeps dense columns when the series does not fit', () => {
    expect(columnWidth(80, 400)).toBe(14);
  });

  it('budgets tick count from plot width', () => {
    expect(chartTickBudget(200)).toBe(3);
    expect(chartTickBudget(720)).toBe(10);
    expect(chartTickBudget(5000)).toBe(12);
  });

  it('picks evenly spaced tick indexes within the budget', () => {
    expect(pickChartTickIndexes(1)).toEqual([0]);
    expect(pickChartTickIndexes(5, 7)).toEqual([0, 1, 2, 3, 4]);
    expect(pickChartTickIndexes(10, 5)).toEqual([0, 2, 5, 7, 9]);
  });

  it('shows date on 1h ticks only when the local day changes', () => {
    const localTs = (year: number, monthIndex: number, day: number, hour: number) =>
      Math.floor(new Date(year, monthIndex, day, hour, 0, 0).getTime() / 1000);

    const day1 = localTs(2026, 6, 18, 10);
    const day1Later = localTs(2026, 6, 18, 15);
    const day2 = localTs(2026, 6, 19, 1);

    const first = fmtChartBucketLabel(day1, '1h', { isFirst: true });
    expect(first.line2).toBeTruthy();

    const sameDay = fmtChartBucketLabel(day1Later, '1h', {
      isFirst: false,
      prevDay: new Date(day1 * 1000),
    });
    expect(sameDay.line2).toBe('');
    expect(sameDay.line1).toBeTruthy();

    const nextDay = fmtChartBucketLabel(day2, '1h', {
      isFirst: false,
      prevDay: new Date(day1Later * 1000),
    });
    expect(nextDay.line2).toBeTruthy();
  });
});

describe('audit display labels', () => {
  it('maps event kinds and decisions to operator language', () => {
    expect(auditKindLabel('scan_input')).toBe('Input scan');
    expect(auditKindLabel('scan_output')).toBe('Answer scan');
    expect(auditKindLabel('retrieval_trace')).toBe('Document retrieval');
    expect(auditKindLabel('query_trace')).toBe('LLM answer');
    expect(auditKindLabel('llm_routed')).toBe('Answer model');
    expect(auditKindLabel('tool_invoke')).toBe('Tool call');
    expect(auditKindLabel('acl_sync')).toBe('Access update');
    expect(auditKindLabel('unknown_kind')).toBe('Unknown Kind');
    expect(decisionLabel('allow')).toBe('Allowed');
    expect(decisionLabel('challenge')).toBe('Challenged');
    expect(decisionLabel('block')).toBe('Blocked');
    expect(auditWhereLabel('rag:user_query')).toBe('Query');
    expect(auditWhereLabel('rag:chunk:chunk-9')).toBe('Retrieved document');
    expect(auditWhereLabel('rag:ingest:doc-1')).toBe('Ingest');
    expect(auditWhereLabel('tool:send_email:body')).toBe('Tool');
    expect(auditWhereLabel('rag:output')).toBe('Answer');
    expect(auditWhereLabel('retrieval.explain')).toBe('Knowledge base');
  });

  it('maps scanner ids to detector names', () => {
    expect(scannerLabel('pii_ner')).toBe('Names and addresses');
    expect(scannerLabel('pii')).toBe('Emails, phones, SSN, SIN, cards');
    expect(scannerLabel('prompt_injection')).toBe('Prompt injection');
    expect(scannerLabel('custom_pattern')).toBe('Custom pattern');
    expect(findingCategoryLabel('sin')).toBe('SIN');
    expect(findingCategoryLabel('ssn')).toBe('SSN');
  });

  it('formats answer-scan detail and click hints', () => {
    expect(formatOutputScanDetail('output scan: clean')).toBe('Answer scan: clean');
    expect(formatOutputScanDetail('output scan: ssn')).toBe('Answer scan: SSN');
    expect(formatOutputScanDetail('output scan: sin')).toBe('Answer scan: SIN');
    expect(auditDetailClickHint('retrieval_trace')).toEqual({
      label: 'click Detail',
      rest: ' for the full trace',
    });
    expect(auditDetailClickHint('scan_output')?.rest).toBe(' for the LLM answer');
  });

  it('humanizes input-scan details including SIN', () => {
    expect(formatAuditEventDetail('scan_input', 'sanitized + warning: person_name, ssn')).toBe(
      'sanitized + warning: Name, SSN',
    );
    expect(formatAuditEventDetail('scan_input', 'sanitized + warning: person_name, sin')).toBe(
      'sanitized + warning: Name, SIN',
    );
  });
});

describe('formatRiskScore', () => {
  it('clips binary float noise to two decimals', () => {
    expect(formatRiskScore(0.799999999)).toBe('0.79');
    expect(formatRiskScore(0.75)).toBe('0.75');
    expect(formatRiskScore(1)).toBe('1');
    expect(formatRiskScore(0)).toBe('0');
    expect(formatRiskScore(0.9)).toBe('0.9');
  });

  it('returns empty for missing scores', () => {
    expect(formatRiskScore(undefined)).toBe('');
    expect(formatRiskScore(null)).toBe('');
    expect(formatRiskScore(Number.NaN)).toBe('');
  });
});
