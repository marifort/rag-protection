import { describe, expect, it } from 'vitest';

import { correlateExfilPairs, EXFIL_HOUR_SECONDS } from './exfilCorrelation';
import type { AuditEvent } from './types';

function event(partial: AuditEvent): AuditEvent {
  return partial;
}

describe('correlateExfilPairs', () => {
  it('returns empty when only one kind is present', () => {
    const pairs = correlateExfilPairs([
      event({ kind: 'extraction_suspected', subject: 'alice.engineer', timestamp: 1000 }),
      event({ kind: 'extraction_suspected', subject: 'alice.engineer', timestamp: 1100 }),
    ]);
    expect(pairs).toEqual([]);
  });

  it('pairs same subject with both kinds in range', () => {
    const pairs = correlateExfilPairs([
      event({
        kind: 'extraction_suspected',
        subject: 'alice.engineer',
        tenant_id: 'default',
        timestamp: 1_752_048_000,
      }),
      event({
        kind: 'canary_triggered',
        subject: 'alice.engineer',
        tenant_id: 'default',
        timestamp: 1_752_048_100,
      }),
    ]);
    expect(pairs).toHaveLength(1);
    expect(pairs[0].subject).toBe('alice.engineer');
    expect(pairs[0].extractionCount).toBe(1);
    expect(pairs[0].canaryCount).toBe(1);
    expect(pairs[0].sameHour).toBe(true);
  });

  it('marks sameHour false when kinds fall in different hour buckets', () => {
    const base = 1_752_048_000;
    const pairs = correlateExfilPairs([
      event({
        kind: 'extraction_suspected',
        subject: 'bob.hr',
        timestamp: base,
      }),
      event({
        kind: 'canary_triggered',
        subject: 'bob.hr',
        timestamp: base + EXFIL_HOUR_SECONDS + 10,
      }),
    ]);
    expect(pairs).toHaveLength(1);
    expect(pairs[0].sameHour).toBe(false);
  });

  it('keeps tenants separate for the same subject', () => {
    const pairs = correlateExfilPairs([
      event({
        kind: 'extraction_suspected',
        subject: 'alice.engineer',
        tenant_id: 'default',
        timestamp: 100,
      }),
      event({
        kind: 'canary_triggered',
        subject: 'alice.engineer',
        tenant_id: 'acme',
        timestamp: 110,
      }),
    ]);
    expect(pairs).toEqual([]);
  });
});
