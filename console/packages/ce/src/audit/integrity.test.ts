import { describe, expect, it } from 'vitest';

import {
  integrityBadgeClass,
  integrityErrorLabel,
  integrityFileMissing,
  integrityStatusLabel,
} from './integrity';

describe('integrityFileMissing', () => {
  it('detects an unset JSONL sink', () => {
    expect(
      integrityFileMissing({
        valid: false,
        events_checked: 0,
        error: 'no audit file configured',
      }),
    ).toBe(true);
  });

  it('detects a configured path that is not on disk', () => {
    expect(
      integrityFileMissing({
        valid: false,
        events_checked: 0,
        error: 'file not found: /data/audit.jsonl',
        audit_file: '/data/audit.jsonl',
      }),
    ).toBe(true);
  });

  it('does not treat a broken chain as missing', () => {
    expect(
      integrityFileMissing({
        valid: false,
        events_checked: 3,
        error: 'event_hash mismatch',
      }),
    ).toBe(false);
  });
});

describe('integrityStatusLabel', () => {
  it('shows not configured instead of invalid when the file is missing', () => {
    expect(
      integrityStatusLabel({
        valid: false,
        error: 'no audit file configured',
      }),
    ).toBe('Not configured');
    expect(
      integrityStatusLabel({
        valid: false,
        error: 'file not found: /data/audit.jsonl',
      }),
    ).toBe('Not configured');
  });

  it('still labels a broken chain as invalid', () => {
    expect(
      integrityStatusLabel({
        valid: false,
        error: 'prev_hash mismatch',
      }),
    ).toBe('Invalid · the log may have been tampered with');
  });
});

describe('integrityBadgeClass', () => {
  it('uses warn for a missing file and bad for tamper', () => {
    expect(integrityBadgeClass({ valid: false, error: 'no audit file configured' })).toBe('warn');
    expect(integrityBadgeClass({ valid: true, events_checked: 2 })).toBe('ok');
    expect(integrityBadgeClass({ valid: false, error: 'event_hash mismatch' })).toBe('bad');
  });
});

describe('integrityErrorLabel', () => {
  it('explains a missing file without API wording', () => {
    expect(integrityErrorLabel({ error: 'no audit file configured' })).toBe(
      'No audit log file is configured',
    );
    expect(integrityErrorLabel({ error: 'file not found: /data/audit.jsonl' })).toBe(
      'Audit log file was not found',
    );
    expect(integrityErrorLabel({ error: 'prev_hash mismatch' })).toBe('prev_hash mismatch');
    expect(integrityErrorLabel({ error: null })).toBe('—');
  });
});
