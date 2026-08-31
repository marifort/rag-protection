import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  useAuth,
  useStatsRange,
  useToast,
  useWorkspaceNav,
} from '@rag-protection/console-core';

import { useRefresh } from '../refresh/RefreshContext';
import { correlateExfilPairs, type ExfilPair } from './exfilCorrelation';
import { fmtTs } from './format';
import type { AuditEvent, AuditListResponse } from './types';

type ExfilCorrelationStripProps = {
  active: boolean;
  /** When true, omit navigate-to-Audit (already on Audit). */
  embeddedInAudit?: boolean;
  onOpenSubject?: (subject: string) => void;
};

async function fetchKindEvents(
  api: { fetchJson: <T>(path: string, init?: RequestInit) => Promise<T> },
  tenantQuery: (path: string) => string,
  adminFetchInit: () => RequestInit,
  kind: string,
  fromTs: number,
  toTs: number,
): Promise<AuditEvent[]> {
  const params = new URLSearchParams({
    kind,
    from_ts: String(fromTs),
    to_ts: String(toTs),
    offset: '0',
    limit: '100',
  });
  const body = await api.fetchJson<AuditListResponse>(
    tenantQuery(`/admin/audit/events?${params}`),
    adminFetchInit(),
  );
  return Array.isArray(body.events) ? body.events : [];
}

export function ExfilCorrelationStrip({
  active,
  embeddedInAudit = false,
  onOpenSubject,
}: ExfilCorrelationStripProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { window, getWindow } = useStatsRange();
  const { tick } = useRefresh();
  const { navigateTo } = useWorkspaceNav();
  const { toast } = useToast();
  const [pairs, setPairs] = useState<ExfilPair[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      const silent = !!opts?.silent;
      if (!adminToken.trim()) {
        setPairs([]);
        setError('');
        return;
      }
      if (!silent) setLoading(true);
      const win = getWindow();
      try {
        const [extraction, canary] = await Promise.all([
          fetchKindEvents(api, tenantQuery, adminFetchInit, 'extraction_suspected', win.from_ts, win.to_ts),
          fetchKindEvents(api, tenantQuery, adminFetchInit, 'canary_triggered', win.from_ts, win.to_ts),
        ]);
        const next = correlateExfilPairs([...extraction, ...canary]);
        setPairs((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
        setError('');
      } catch (err) {
        if (!silent) setPairs([]);
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [adminFetchInit, adminToken, api, getWindow, tenantQuery],
  );

  useEffect(() => {
    if (!active) return;
    void load({ silent: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, adminToken, window.from_ts, window.to_ts]);

  useEffect(() => {
    if (!active || !adminToken.trim()) return;
    void load({ silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, adminToken, tick, window.from_ts, window.to_ts]);

  if (!active) return null;

  function openSubject(subject: string) {
    if (onOpenSubject) {
      onOpenSubject(subject);
      return;
    }
    navigateTo('audit', { type: 'filter-exfil', subject });
    toast(`Audit filtered to subject=${subject} (extraction + canary kinds cleared)`);
  }

  return (
    <div
      className="card"
      style={{
        border: pairs.length
          ? '1px solid color-mix(in srgb, var(--bad, #ef4444) 45%, var(--line))'
          : undefined,
        background: pairs.length
          ? 'linear-gradient(180deg, color-mix(in srgb, var(--panel, #111) 90%, var(--bad, #ef4444) 10%), var(--panel, #111))'
          : undefined,
      }}
    >
      <h2>Suspected data theft</h2>
      <p>
        Users in this time range who both scraped the knowledge base and hit a canary document. That
        combination is a high-confidence theft signal. The timing badge is <strong>same hour</strong> when
        both happened within one hour; otherwise <strong>range only</strong>.
      </p>
      {!adminToken.trim() ? (
        <p className="muted">Sign in with an admin token to load this signal.</p>
      ) : null}
      {error ? <p className="error-text">{error}</p> : null}
      <div className="row-actions" style={{ marginBottom: 10 }}>
        <button
          type="button"
          disabled={loading || !adminToken.trim()}
          onClick={() => void load({ silent: false })}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
        <span className="pill">{window.label}</span>
        {pairs.length ? (
          <span className="pill bad">{pairs.length} high-confidence</span>
        ) : (
          <span className="pill ok">0 pairs</span>
        )}
      </div>
      {pairs.length ? (
        <div className="table-wrap">
          <table className="audit-findings-table">
            <thead>
              <tr>
                {['User', 'Tenant', 'Scrapes', 'Canary hits', 'Timing', 'Last signal', ''].map(
                  (label) => (
                    <th key={label || 'actions'}>{label}</th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {pairs.map((pair) => (
                <tr key={`${pair.tenantId}:${pair.subject}`}>
                  <td>
                    <code>{pair.subject}</code>
                  </td>
                  <td>{pair.tenantId}</td>
                  <td>{pair.extractionCount}</td>
                  <td>{pair.canaryCount}</td>
                  <td>
                    <span className={`pill ${pair.sameHour ? 'bad' : 'warn'}`}>
                      {pair.sameHour ? 'same hour' : 'range only'}
                    </span>
                  </td>
                  <td>{fmtTs(pair.lastTs)}</td>
                  <td>
                    <button type="button" className="primary" onClick={() => openSubject(pair.subject)}>
                      {embeddedInAudit ? 'Filter table' : 'Open in Audit'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="dlp-hint" style={{ margin: 0 }}>
          {adminToken.trim()
            ? loading
              ? 'Loading…'
              : 'No high-confidence pairs in this time range. A pair appears when the same user both scraped the knowledge base and hit a canary document. If you expected to see one, widen the time range.'
            : null}
        </p>
      )}
      <p className="dlp-hint" style={{ marginTop: 12 }}>
        Review these users in Audit. Same-hour pairs are the strongest signal.
      </p>
    </div>
  );
}
