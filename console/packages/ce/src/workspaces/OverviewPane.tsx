import { useEffect, useState } from 'react';

import {
  ApiError,
  DEFAULT_OPERATION_RESULT,
  useAuth,
  useOperationResult,
  useStatsRange,
  type HealthResponse,
  type WorkspaceComponentProps,
} from '@rag-protection/console-core';

import { useRefresh } from '../refresh/RefreshContext';
import { ExfilCorrelationStrip } from '../audit/ExfilCorrelationStrip';

function parseMetricLabels(metricPart: string) {
  const out: Record<string, string> = {};
  const matches = metricPart.matchAll(/([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"/g);
  for (const match of matches) out[match[1]] = match[2];
  return out;
}

function parsePrometheusCounters(text: string) {
  const totals = { allowed: 0, blocked: 0, ingest: 0 };
  for (const line of text.split('\n')) {
    if (!line || line.startsWith('#')) continue;
    const parts = line.trim().split(/\s+/);
    if (parts.length < 2) continue;
    const metric = parts[0];
    const value = Number(parts[parts.length - 1]);
    if (!Number.isFinite(value)) continue;
    if (metric.startsWith('rag_queries_total{')) {
      const labels = parseMetricLabels(metric);
      if (labels.decision === 'allowed') totals.allowed += value;
      else if (labels.decision === 'blocked') totals.blocked += value;
    } else if (metric === 'rag_ingest_total' || metric.startsWith('rag_ingest_total ')) {
      totals.ingest += value;
    }
  }
  return totals;
}

type OverviewStats = {
  challenges_pending?: number;
  ingest_quarantined?: number;
  challenge_approved?: number;
  challenge_rejected?: number;
};

function MetricsBars({
  metrics,
  challengesPending,
}: {
  metrics: { allowed: number; blocked: number; ingest: number };
  challengesPending: number | null;
}) {
  const rows = [
    { label: 'Queries allowed', value: metrics.allowed, cls: '' },
    { label: 'Queries blocked', value: metrics.blocked, cls: metrics.blocked > 0 ? 'warn' : '' },
    { label: 'Documents ingested', value: metrics.ingest, cls: '' },
    ...(challengesPending == null
      ? []
      : [
          {
            label: 'Awaiting review',
            value: challengesPending,
            cls: challengesPending > 0 ? 'warn' : '',
          },
        ]),
  ];
  const max = Math.max(1, ...rows.map((row) => row.value));

  return (
    <div className="bars">
      {rows.map((row) => (
        <div key={row.label} className="bar-row">
          <div className="bar-head">
            <span>{row.label}</span>
            <span>{row.value}</span>
          </div>
          <div className="bar-track">
            <div
              className={`bar-fill ${row.cls}`}
              style={{ width: `${Math.max(4, (row.value / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function OverviewPane({ active }: WorkspaceComponentProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { getWindow } = useStatsRange();
  const { tick } = useRefresh();
  const { lastOperation } = useOperationResult();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [metrics, setMetrics] = useState<{ allowed: number; blocked: number; ingest: number } | null>(
    null,
  );
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!active) return;
    let cancelled = false;

    async function load() {
      setError('');
      try {
        const [healthBody, metricsText] = await Promise.all([
          api.health(),
          fetch(api.baseUrl + '/metrics').then((response) => response.text()),
        ]);
        if (cancelled) return;
        setHealth(healthBody);
        setMetrics(parsePrometheusCounters(metricsText));
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [active, api, tick]);

  useEffect(() => {
    if (!active || !adminToken) {
      setOverviewStats(null);
      return;
    }
    let cancelled = false;
    async function loadStats() {
      const win = getWindow();
      try {
        const body = await api.fetchJson<OverviewStats>(
          tenantQuery(`/admin/overview/stats?from_ts=${win.from_ts}&to_ts=${win.to_ts}`),
          adminFetchInit(),
        );
        if (!cancelled) setOverviewStats(body);
      } catch {
        if (!cancelled) setOverviewStats(null);
      }
    }
    void loadStats();
    return () => {
      cancelled = true;
    };
  }, [active, adminFetchInit, adminToken, api, getWindow, tenantQuery, tick]);

  const resultText = lastOperation
    ? JSON.stringify(lastOperation, null, 2)
    : DEFAULT_OPERATION_RESULT;
  const challengesPending =
    overviewStats?.challenges_pending == null ? null : Number(overviewStats.challenges_pending) || 0;

  return (
    <div className="workspace-pane active">
      <ExfilCorrelationStrip active={active} />
      <div className="grid-2">
        <div className="card">
          <h2>Service status</h2>
          <p>
            Current health of this deployment.
          </p>
          {error ? <p className="error-text">{error}</p> : null}
          <pre>{health ? JSON.stringify(health, null, 2) : 'loading…'}</pre>
        </div>

        <div className="card">
          <h2>Totals since restart</h2>
          <p>
            Queries allowed, blocked, and documents ingested since the last service restart. Changing the
            time range above does not change these numbers. With an admin token,{' '}
            <strong>Awaiting review</strong> is how many items are waiting in the review queue.
          </p>
          {metrics ? (
            <MetricsBars metrics={metrics} challengesPending={challengesPending} />
          ) : (
            <p className="muted">loading…</p>
          )}
          {adminToken && overviewStats ? (
            <p className="dlp-hint" style={{ marginTop: 12 }}>
              In this time range: quarantined ingest {overviewStats.ingest_quarantined ?? 0} · approved{' '}
              {overviewStats.challenge_approved ?? 0} · rejected {overviewStats.challenge_rejected ?? 0}.
              Review held documents in <strong>Documents & Ingest</strong>.
            </p>
          ) : adminToken ? null : (
            <p className="muted" style={{ marginTop: 12 }}>
              Sign in with an admin token to show items awaiting review and ingest quarantine totals.
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Last result</h2>
        <pre>{resultText}</pre>
      </div>
    </div>
  );
}
