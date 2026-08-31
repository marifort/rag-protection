import { useState } from 'react';

import { ApiError, useAuth, useToast } from '@rag-protection/console-core';

import {
  integrityBadgeClass,
  integrityErrorLabel,
  integrityFileMissing,
  integrityStatusLabel,
  type AuditIntegrityResult,
} from './integrity';

type AuditIntegrityCardProps = {
  active: boolean;
};

export function AuditIntegrityCard({ active }: AuditIntegrityCardProps) {
  const { api, adminToken, adminFetchInit } = useAuth();
  const { toast } = useToast();
  const [verifying, setVerifying] = useState(false);
  const [limit, setLimit] = useState('');
  const [result, setResult] = useState<AuditIntegrityResult | null>(null);

  if (!active) return null;

  async function verifyChain() {
    if (!adminToken) {
      toast('Sign in with an admin token to check log integrity.', 'err');
      return;
    }
    setVerifying(true);
    try {
      const params = new URLSearchParams();
      const parsed = Number(limit);
      if (Number.isFinite(parsed) && parsed > 0) {
        params.set('limit', String(Math.floor(parsed)));
      }
      const path = params.size
        ? `/admin/audit/integrity/verify?${params}`
        : '/admin/audit/integrity/verify';
      const body = await api.fetchJson<AuditIntegrityResult>(path, adminFetchInit());
      setResult(body);
      if (integrityFileMissing(body)) {
        return;
      }
      if (body.valid) {
        toast(integrityStatusLabel(body));
      } else {
        toast(integrityStatusLabel(body), 'err');
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setResult(null);
      toast(message, 'err');
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="card">
      <h2>Log integrity</h2>
      <p>
        Check that the audit log has not been tampered with. Turn on log integrity in Policy (Edit →
        Advanced Features → Audit).
      </p>
      <div className="row-actions" style={{ marginBottom: 10 }}>
        <label style={{ display: 'inline-grid', gap: 4 }}>
          Events to check
          <input
            type="number"
            min={1}
            max={100000}
            value={limit}
            placeholder="All events"
            onChange={(event) => setLimit(event.target.value)}
            style={{ width: 110 }}
            aria-label="events to check"
          />
        </label>
        <button
          type="button"
          className="primary"
          disabled={verifying || !adminToken}
          onClick={() => void verifyChain()}
        >
          {verifying ? 'Checking…' : 'Check integrity'}
        </button>
        <span className={`pill ${integrityBadgeClass(result)}`} data-testid="integrity-badge">
          {integrityStatusLabel(result)}
        </span>
      </div>
      {result ? (
        <dl className="verdict-kv" style={{ margin: 0 }}>
          <dt>Valid</dt>
          <dd>
            {integrityFileMissing(result) ? (
              <span className="pill warn">—</span>
            ) : (
              <span className={`pill ${result.valid ? 'ok' : 'bad'}`}>
                {result.valid ? 'Yes' : 'No'}
              </span>
            )}
          </dd>
          <dt>Events checked</dt>
          <dd>{result.events_checked ?? 0}</dd>
          <dt>Tamper protection</dt>
          <dd>{result.integrity_chain_enabled ? 'On' : 'Off'}</dd>
          <dt>Error</dt>
          <dd>{integrityErrorLabel(result)}</dd>
          <dt>Broken at line</dt>
          <dd>{result.broken_at_line ?? '—'}</dd>
          <dt>Log file</dt>
          <dd>{result.audit_file || '—'}</dd>
          {result.note ? (
            <>
              <dt>Note</dt>
              <dd>{result.note}</dd>
            </>
          ) : null}
        </dl>
      ) : (
        <p className="muted" style={{ margin: 0 }}>
          {!adminToken
            ? 'Sign in with an admin token to check log integrity.'
            : 'Click Check integrity to confirm the log has not been tampered with.'}
        </p>
      )}
    </div>
  );
}
