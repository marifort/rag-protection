import { describe, expect, it } from 'vitest';

import { parseCitationAuditDetail } from './citationDetail';

describe('parseCitationAuditDetail', () => {
  it('parses claims with entailment scores', () => {
    const parsed = parseCitationAuditDetail(
      JSON.stringify({
        summary: '1/2 sentences aligned',
        hard_gate_failed: true,
        unsupported_count: 1,
        coverage_ratio: 0.5,
        claims: [
          {
            sentence: 'Employees receive twenty days of PTO each year.',
            chunk_id: 'faq-pto::0',
            supported: true,
            entailment_score: 0.74,
          },
          {
            sentence: 'Q1 payroll was 4.2 million.',
            chunk_id: null,
            supported: false,
            entailment_score: 0.12,
          },
        ],
        unsupported_claims: [
          {
            sentence: 'Q1 payroll was 4.2 million.',
            chunk_id: null,
            entailment_score: 0.12,
          },
        ],
      }),
    );
    expect(parsed?.coverage_ratio).toBe(0.5);
    expect(parsed?.claims).toHaveLength(2);
    expect(parsed?.claims[0].entailment_score).toBe(0.74);
    expect(parsed?.unsupported_claims).toHaveLength(1);
  });

  it('returns null for plain strings and invalid JSON', () => {
    expect(parseCitationAuditDetail('citation verification failed')).toBeNull();
    expect(parseCitationAuditDetail('{"foo":1}')).toBeNull();
    expect(parseCitationAuditDetail(undefined)).toBeNull();
  });
});
