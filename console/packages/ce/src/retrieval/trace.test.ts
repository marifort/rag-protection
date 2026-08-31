import { describe, expect, it } from 'vitest';

import {
  formatRetrievalTraceSummary,
  outcomeClass,
  outcomeLabel,
  parseRetrievalTraceDetail,
  retrievalReasonLabel,
  sortRetrievalTrace,
  summarizeTrace,
  type RetrievalDecision,
} from './trace';

const SAMPLE: RetrievalDecision[] = [
  { document_id: 'a', outcome: 'selected', score: 0.9 },
  { document_id: 'b', outcome: 'excluded_acl', score: 0 },
  { document_id: 'c', outcome: 'not_in_top_k', score: 0.4 },
  { document_id: 'd', outcome: 'excluded_quarantine', score: 0 },
];

describe('summarizeTrace', () => {
  it('counts outcomes', () => {
    expect(summarizeTrace(SAMPLE)).toEqual({
      candidates: 4,
      selected: 1,
      excluded_acl: 1,
      excluded_quarantine: 1,
      excluded_low_score: 0,
      not_in_top_k: 1,
      other: 0,
    });
  });
});

describe('sortRetrievalTrace', () => {
  it('orders quarantine → ACL → not top-k → selected', () => {
    expect(sortRetrievalTrace(SAMPLE).map((row) => row.document_id)).toEqual(['d', 'b', 'c', 'a']);
  });
});

describe('outcomeClass', () => {
  it('maps outcomes to pill classes', () => {
    expect(outcomeClass('selected')).toBe('ok');
    expect(outcomeClass('excluded_acl')).toBe('bad');
    expect(outcomeClass('not_in_top_k')).toBe('warn');
  });
});

describe('parseRetrievalTraceDetail', () => {
  it('parses audit detail JSON', () => {
    const parsed = parseRetrievalTraceDetail(
      JSON.stringify({
        query_len: 12,
        candidates: 2,
        selected: 1,
        trace: [{ document_id: 'doc-1', outcome: 'selected', score: 1 }],
      }),
    );
    expect(parsed?.candidates).toBe(2);
    expect(parsed?.trace).toHaveLength(1);
    expect(parsed?.trace[0]?.document_id).toBe('doc-1');
  });

  it('returns null for invalid detail', () => {
    expect(parseRetrievalTraceDetail('not-json')).toBeNull();
    expect(parseRetrievalTraceDetail('{"trace":null}')).toBeNull();
    expect(parseRetrievalTraceDetail(undefined)).toBeNull();
  });
});

describe('retrieval display labels', () => {
  it('uses operator language for outcomes and reasons', () => {
    expect(outcomeLabel('selected')).toBe('Used');
    expect(outcomeLabel('excluded_acl')).toBe('Access denied');
    expect(outcomeLabel('excluded_low_score')).toBe('Below score');
    expect(retrievalReasonLabel('no token overlap with query')).toBe(
      'No words in common with the question',
    );
    expect(retrievalReasonLabel('required groups ["hr"]')).toBe('Needs access: ["hr"]');
    expect(retrievalReasonLabel('top_4 by score')).toBe('Ranked in the top 4');
  });

  it('summarizes audit retrieval JSON for the event list', () => {
    expect(
      formatRetrievalTraceSummary(
        JSON.stringify({
          candidates: 42,
          selected: 4,
          trace: [
            { outcome: 'selected' },
            { outcome: 'selected' },
            { outcome: 'selected' },
            { outcome: 'selected' },
            { outcome: 'excluded_low_score' },
            { outcome: 'excluded_low_score' },
          ],
        }),
      ),
    ).toBe('4 used of 42 considered · 2 below score');
  });
});
