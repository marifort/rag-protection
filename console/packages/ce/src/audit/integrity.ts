export type AuditIntegrityResult = {
  valid?: boolean;
  events_checked?: number;
  error?: string | null;
  broken_at_line?: number | null;
  last_hash?: string | null;
  integrity_chain_enabled?: boolean;
  audit_file?: string | null;
  note?: string | null;
};

export function integrityFileMissing(result: AuditIntegrityResult | null): boolean {
  if (!result) return false;
  const error = String(result.error || '').toLowerCase();
  return error.includes('no audit file configured') || error.startsWith('file not found');
}

export function integrityBadgeClass(result: AuditIntegrityResult | null) {
  if (!result) return '';
  if (integrityFileMissing(result)) return 'warn';
  if (result.valid) return 'ok';
  return 'bad';
}

export function integrityErrorLabel(result: AuditIntegrityResult | null) {
  if (!result?.error) return '—';
  const error = String(result.error);
  const lower = error.toLowerCase();
  if (lower.includes('no audit file configured')) return 'No audit log file is configured';
  if (lower.startsWith('file not found')) return 'Audit log file was not found';
  return error;
}

export function integrityStatusLabel(result: AuditIntegrityResult | null) {
  if (!result) return 'Not verified';
  if (integrityFileMissing(result)) return 'Not configured';
  if (result.valid) {
    const n = Number(result.events_checked) || 0;
    return `Valid · ${n.toLocaleString()} event${n === 1 ? '' : 's'} checked`;
  }
  return 'Invalid · the log may have been tampered with';
}
