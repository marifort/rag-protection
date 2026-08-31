import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  useAuth,
  useStatsRange,
  useToast,
  useWorkspaceNav,
  type WorkspaceComponentProps,
} from '@rag-protection/console-core';

import { AuditAnalyticsCard } from '../audit/AuditAnalyticsCard';
import { AuditEventDrawer } from '../audit/AuditEventDrawer';
import { AuditIntegrityCard } from '../audit/AuditIntegrityCard';
import { ExfilCorrelationStrip } from '../audit/ExfilCorrelationStrip';
import {
  auditDetailClickHint,
  AUDIT_WHERE_FILTERS,
  auditEventPin,
  auditKindLabel,
  auditWhereLabel,
  decisionClass,
  decisionLabel,
  findLatestQueryTraceIndex,
  formatAuditEventDetail,
  formatFindingSummary,
  formatRiskScore,
  fmtTs,
  hasAuditDebug,
} from '../audit/format';
import type { AuditDrilldown, AuditEvent, AuditListResponse } from '../audit/types';
import { useRefresh } from '../refresh/RefreshContext';

const KIND_PRESETS = [
  'ingest_completed',
  'challenge_approved',
  'challenge_rejected',
  'scan_input',
  'scan_output',
  'tool_invoke',
  'tool_challenge_approved',
  'tool_challenge_denied',
  'extraction_suspected',
  'canary_triggered',
  'retrieval_trace',
  'permission_drift',
  'connector_sync',
  'acl_sync',
  'llm_routed',
  'query_trace',
] as const;

function AuditDetailCell({ row }: { row: AuditEvent }) {
  const summary = formatAuditEventDetail(row.kind, row.detail);
  const hint = auditDetailClickHint(row.kind);
  if (!hint) return <>{summary}</>;
  return (
    <>
      <span className="audit-detail-click-hint">{hint.label}</span>
      {hint.rest}
      {summary ? ` · ${summary}` : ''}
    </>
  );
}

export function AuditLogPane({ active }: WorkspaceComponentProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { toast } = useToast();
  const { consumePendingAction } = useWorkspaceNav();
  const { window, getWindow } = useStatsRange();
  const { tick, bump } = useRefresh();
  const [drilldown, setDrilldown] = useState<AuditDrilldown | null>(null);
  const [kind, setKind] = useState('');
  const [decision, setDecision] = useState('');
  const [search, setSearch] = useState('');
  const [where, setWhere] = useState('');
  const [appliedKind, setAppliedKind] = useState('');
  const [appliedDecision, setAppliedDecision] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [appliedWhere, setAppliedWhere] = useState('');
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(50);
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [selectedPin, setSelectedPin] = useState('');
  const [forcedRow, setForcedRow] = useState<AuditEvent | null>(null);

  const effectiveLabel = drilldown ? drilldown.label : window.label;

  const openQueryTrace = useCallback(
    async (match: { sinceTs: number; subject: string }) => {
      if (!adminToken) return;
      const waitMs = [0, 150, 350, 700, 1200];
      let traceRow: AuditEvent | null = null;
      try {
        for (let attempt = 0; attempt < waitMs.length; attempt += 1) {
          if (waitMs[attempt] > 0) {
            await new Promise((resolve) => globalThis.setTimeout(resolve, waitMs[attempt]));
          }
          const win = getWindow();
          const params = new URLSearchParams({
            from_ts: String(win.from_ts),
            to_ts: String(win.to_ts),
            offset: '0',
            limit: '20',
            kind: 'query_trace',
          });
          const body = await api.fetchJson<AuditListResponse>(
            tenantQuery(`/admin/audit/events?${params}`),
            adminFetchInit(),
          );
          const nextRows = Array.isArray(body.events) ? body.events : [];
          const traceIdx = findLatestQueryTraceIndex(nextRows, match);
          if (traceIdx >= 0) {
            traceRow = nextRows[traceIdx] ?? null;
            break;
          }
        }
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        toast(message, 'err');
        return;
      }

      if (!traceRow) {
        toast('audit_debug enabled — query_trace not found yet; refresh Audit Log.', 'err');
        return;
      }

      setDrilldown(null);
      setOffset(0);
      setSelectedPin(auditEventPin(traceRow));
      setForcedRow(traceRow);
      setSelectedIndex(-1);
      bump();
      toast('Query trace opened (debug previews).');
    },
    [adminFetchInit, adminToken, api, bump, getWindow, tenantQuery, toast],
  );

  useEffect(() => {
    if (!active) return;
    if (!adminToken) {
      setRows([]);
      setTotal(0);
      setError('');
      setSelectedIndex(-1);
      return;
    }

    let cancelled = false;

    async function load() {
      setError('');
      // Recompute the time window on every fetch so auto-refresh picks up
      // queries that arrived after mount. Drilldown windows are fixed buckets.
      const win = drilldown
        ? { from_ts: drilldown.from_ts, to_ts: drilldown.to_ts }
        : getWindow();
      const params = new URLSearchParams({
        from_ts: String(win.from_ts),
        to_ts: String(win.to_ts),
        offset: String(offset),
        limit: String(limit),
      });
      if (appliedKind.trim()) params.set('kind', appliedKind.trim());
      if (appliedDecision) params.set('decision', appliedDecision);
      if (appliedSearch.trim()) params.set('search', appliedSearch.trim());
      if (appliedWhere.trim()) params.set('where', appliedWhere.trim());
      try {
        const body = await api.fetchJson<AuditListResponse>(tenantQuery(`/admin/audit/events?${params}`), {
          ...adminFetchInit(),
        });
        if (cancelled) return;
        const nextRows = Array.isArray(body.events) ? body.events : [];
        setRows(nextRows);
        setTotal(Number(body.total) || 0);
        if (selectedPin) {
          const idx = nextRows.findIndex((row) => auditEventPin(row) === selectedPin);
          setSelectedIndex(idx);
          if (idx >= 0) setForcedRow(null);
        } else {
          setSelectedIndex(-1);
          setForcedRow(null);
        }
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
        setRows([]);
        setTotal(0);
        setSelectedIndex(-1);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [
    active,
    adminFetchInit,
    adminToken,
    api,
    appliedDecision,
    appliedKind,
    appliedSearch,
    appliedWhere,
    drilldown,
    getWindow,
    limit,
    offset,
    selectedPin,
    tenantQuery,
    tick,
  ]);

  function handleDrilldown(next: AuditDrilldown | null) {
    if (next === null) {
      // Chart colored-bar clicks also apply decision; undo that with the time bucket.
      if (drilldown?.decision) {
        setDecision('');
        setAppliedDecision('');
      }
      setDrilldown(null);
    } else {
      if (next.decision) {
        setDecision(next.decision);
        setAppliedDecision(next.decision);
      }
      setDrilldown(next);
    }
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
  }

  function applyFilters() {
    setAppliedKind(kind);
    setAppliedDecision(decision);
    setAppliedSearch(search);
    setAppliedWhere(where);
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
    bump();
  }

  function clearFilters() {
    setKind('');
    setDecision('');
    setSearch('');
    setWhere('');
    setAppliedKind('');
    setAppliedDecision('');
    setAppliedSearch('');
    setAppliedWhere('');
    setDrilldown(null);
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
    bump();
  }

  function applyKindPreset(nextKind: string) {
    setKind(nextKind);
    setAppliedKind(nextKind);
    setWhere('');
    setAppliedWhere('');
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
    bump();
  }

  function applyWherePreset(nextWhere: string) {
    if (nextWhere === 'output') {
      setKind('scan_output');
      setAppliedKind('scan_output');
    } else {
      setKind('scan_input');
      setAppliedKind('scan_input');
    }
    setWhere(nextWhere);
    setAppliedWhere(nextWhere);
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
    bump();
  }

  function applyExfilSubjectFilter(subject: string) {
    setSearch(subject);
    setAppliedSearch(subject);
    setKind('');
    setAppliedKind('');
    setDecision('');
    setAppliedDecision('');
    setWhere('');
    setAppliedWhere('');
    setDrilldown(null);
    setOffset(0);
    setSelectedIndex(-1);
    setSelectedPin('');
    bump();
  }

  function openDrawer(index: number) {
    const row = rows[index];
    if (!row) return;
    setSelectedIndex(index);
    setSelectedPin(auditEventPin(row));
  }

  function closeDrawer() {
    setSelectedIndex(-1);
    setSelectedPin('');
    setForcedRow(null);
  }

  async function exportAudit() {
    if (!adminToken) {
      toast('Set admin bearer token first.', 'err');
      return;
    }
    setExporting(true);
    setError('');
    try {
      const response = await fetch(`${api.baseUrl}${tenantQuery('/admin/audit/export')}`, adminFetchInit());
      if (!response.ok) {
        const text = await response.text();
        let detail = response.statusText;
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          if (parsed.detail) detail = parsed.detail;
        } catch {
          /* keep status text */
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'audit-export.jsonl';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast('Audit export downloaded.');
    } catch (err) {
      const message = String(err instanceof Error ? err.message : err);
      setError(message);
      toast(message, 'err');
    } finally {
      setExporting(false);
    }
  }

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + limit, total);
  const selectedRow =
    selectedIndex >= 0
      ? rows[selectedIndex]
      : forcedRow && selectedPin && auditEventPin(forcedRow) === selectedPin
        ? forcedRow
        : null;

  useEffect(() => {
    if (!active) {
      setSelectedIndex(-1);
      setSelectedPin('');
      setForcedRow(null);
      return;
    }
    const action = consumePendingAction('audit');
    if (!action) return;
    if (action.type === 'open-trace' && action.match && typeof action.match === 'object') {
      const match = action.match as { sinceTs: number; subject: string };
      void openQueryTrace(match);
    }
    if (action.type === 'filter-kind' && typeof action.kind === 'string') {
      applyKindPreset(action.kind);
      toast(`Filtered Audit Log to kind=${action.kind}`);
    }
    if (action.type === 'filter-exfil' && typeof action.subject === 'string') {
      applyExfilSubjectFilter(action.subject);
      toast(`Exfil pair — showing events for subject=${action.subject}`);
    }
  }, [active, consumePendingAction, openQueryTrace, toast]);

  return (
    <>
      <ExfilCorrelationStrip
        active={active}
        embeddedInAudit
        onOpenSubject={(subject) => {
          applyExfilSubjectFilter(subject);
          toast(`Filtered events to ${subject}`);
        }}
      />
      <AuditAnalyticsCard active={active} drilldown={drilldown} onDrilldown={handleDrilldown} />
      <AuditIntegrityCard active={active} />

      <div className="card">
        <h2>Audit events</h2>
        <p>
          Events in the selected time range. Held ingest documents go from review to approved or
          rejected. <strong>Document retrieval</strong> is which knowledge-base passages were kept.{' '}
          <strong>Answer scan</strong> and <strong>LLM answer</strong> are the model’s reply after
          generation. <strong>Where</strong> is the text that was scanned: the question, a retrieved
          document, ingest, a tool argument, or the answer. Click a colored bar in{' '}
          <strong>Audit activity</strong> above to filter by time (table column headers are labels
          only). Click a row or the highlighted <strong>click Detail</strong> hint to inspect the full
          trace.
        </p>
        {!adminToken ? (
          <p className="muted">Sign in with an admin token to browse audit events.</p>
        ) : null}
        <div className="row-actions" style={{ marginBottom: 10, flexWrap: 'wrap' }}>
          {KIND_PRESETS.map((kindPreset) => (
            <button
              key={kindPreset}
              type="button"
              className={`preset-chip${appliedKind === kindPreset ? ' active' : ''}`}
              onClick={() => applyKindPreset(kindPreset)}
              disabled={!adminToken}
            >
              {auditKindLabel(kindPreset)}
            </button>
          ))}
        </div>
        <div className="row-actions" style={{ marginBottom: 10, flexWrap: 'wrap' }}>
          <span className="muted" style={{ alignSelf: 'center' }}>
            Where
          </span>
          {AUDIT_WHERE_FILTERS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`preset-chip${appliedWhere === preset.id ? ' active' : ''}`}
              onClick={() => applyWherePreset(preset.id)}
              disabled={!adminToken}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="audit-list-toolbar">
          <label>
            Search
            <input
              type="search"
              value={search}
              placeholder="user, detail, labels…"
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyFilters();
              }}
            />
          </label>
          <label>
            Type
            <input
              value={kind}
              placeholder="event type"
              onChange={(event) => setKind(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyFilters();
              }}
            />
          </label>
          <label>
            Decision
            <select value={decision} onChange={(event) => setDecision(event.target.value)}>
              <option value="">Any</option>
              <option value="allow">Allowed</option>
              <option value="challenge">Challenged</option>
              <option value="block">Blocked</option>
            </select>
          </label>
          <button type="button" onClick={applyFilters}>
            Apply filters
          </button>
          <button type="button" onClick={clearFilters}>
            Clear
          </button>
          <button type="button" onClick={() => handleDrilldown(null)}>
            Clear chart filter
          </button>
          <button type="button" className="primary" disabled={exporting || !adminToken} onClick={() => void exportAudit()}>
            {exporting ? 'Exporting…' : 'Download export'}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="audit-list-summary">
          {adminToken
            ? `${total.toLocaleString()} event${total === 1 ? '' : 's'} in ${effectiveLabel} · showing ${pageStart}-${pageEnd}`
            : 'Sign in with an admin token to browse audit events in the selected range.'}
        </div>
        <div className="audit-table-wrap">
          <table className="audit-table">
            <colgroup>
              <col className="col-time" />
              <col className="col-kind" />
              <col className="col-where" />
              <col className="col-decision" />
              <col className="col-risk" />
              <col className="col-labels" />
              <col className="col-subject" />
              <col className="col-detail" />
            </colgroup>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Where</th>
                <th>Decision</th>
                <th>Risk</th>
                <th>Findings</th>
                <th>User</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((row, index) => (
                  <tr
                    key={`${row.timestamp}-${row.kind}-${index}`}
                    className={`audit-row-clickable${selectedIndex === index ? ' audit-row-selected' : ''}`}
                    onClick={() => openDrawer(index)}
                  >
                    <td className="col-time">{fmtTs(row.timestamp)}</td>
                    <td className="col-kind">
                      <span className="audit-kind-cell">
                        {auditKindLabel(row.kind)}
                        {hasAuditDebug(row) ? <span className="pill debug">debug</span> : null}
                      </span>
                    </td>
                    <td className="col-where">{auditWhereLabel(row.source) || '—'}</td>
                    <td className="col-decision">
                      <span className={`pill ${decisionClass(row.decision)}`}>{decisionLabel(row.decision)}</span>
                    </td>
                    <td className="col-risk">{formatRiskScore(row.risk_score)}</td>
                    <td className="col-labels">{formatFindingSummary(row.findings) || '—'}</td>
                    <td className="col-subject">{row.subject}</td>
                    <td
                      className={`col-detail${auditDetailClickHint(row.kind) ? ' col-detail-rich' : ''}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        openDrawer(index);
                      }}
                    >
                      <AuditDetailCell row={row} />
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                    <td colSpan={8}>
                    {!adminToken
                      ? 'Sign in with an admin token to browse events.'
                      : appliedKind === 'acl_sync'
                        ? 'No access-update events in this range. Routine unchanged checks are sampled out. Events appear when groups change or mapping fails.'
                        : appliedKind === 'connector_sync'
                          ? 'No connector-sync events in this range. Routine heartbeats are sampled out; failures and access updates still record.'
                          : 'No audit events match the selected range and filters.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="audit-pagination">
          <label>
            Per page
            <select
              value={limit}
              onChange={(event) => {
                setLimit(Number(event.target.value) || 50);
                setOffset(0);
              }}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <span>
            {pageStart}-{pageEnd} of {total}
          </span>
          <button type="button" disabled={offset <= 0} onClick={() => setOffset((current) => Math.max(0, current - limit))}>
            Previous
          </button>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => setOffset((current) => current + limit)}
          >
            Next
          </button>
          <button type="button" onClick={bump}>
            Refresh table
          </button>
        </div>
      </div>

      <AuditEventDrawer row={selectedRow} onClose={closeDrawer} />
    </>
  );
}
