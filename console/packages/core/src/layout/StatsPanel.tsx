import { useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { STATS_RANGE_OPTIONS, useStatsRange } from './StatsRangeContext';

type OverviewStats = {
  documents_current?: number;
  challenges_pending?: number;
  queries_allowed?: number;
  queries_blocked?: number;
  ingest_total?: number;
  ingest_quarantined?: number;
  challenge_approved?: number;
  challenge_rejected?: number;
  audit_events_total?: number;
};

const DOCUMENTS_HINT = 'Documents is the full tenant library, not limited by your access';
const QUARANTINED_HINT = 'Quarantined is items awaiting review';

export type StatsPanelProps = {
  refreshTick?: number;
};

export function StatsPanel({ refreshTick = 0 }: StatsPanelProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { range, setRange, getWindow } = useStatsRange();
  const [caption, setCaption] = useState(
    `Last 7 days · ${DOCUMENTS_HINT}`,
  );
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [docCount, setDocCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const health = await api.health();
        if (!cancelled) {
          setDocCount(Number(health.documents) || 0);
        }
      } catch {
        if (!cancelled) setDocCount(null);
      }
    }

    void loadHealth();
    return () => {
      cancelled = true;
    };
  }, [api, refreshTick]);

  useEffect(() => {
    const option = STATS_RANGE_OPTIONS.find((item) => item.value === range);
    if (!adminToken) {
      setStats(null);
      setCaption(
        `Sign in with an admin token for stats in this time range · ${DOCUMENTS_HINT}`,
      );
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
        if (cancelled) return;
        setStats(body);
        setCaption(
          `${option?.caption ?? 'Stats'} · ${DOCUMENTS_HINT} · ${QUARANTINED_HINT}`,
        );
      } catch (err: unknown) {
        if (cancelled) return;
        const hint =
          err instanceof ApiError && err.status === 404
            ? 'Overview stats API not found — restart the proxy container'
            : 'Failed to load overview stats';
        setStats(null);
        setCaption(`${hint} · ${DOCUMENTS_HINT}`);
      }
    }

    void loadStats();
    return () => {
      cancelled = true;
    };
  }, [adminFetchInit, adminToken, api, getWindow, range, refreshTick, tenantQuery]);

  const documents = stats?.documents_current ?? docCount ?? 0;
  const challengesPending = stats?.challenges_pending;

  return (
    <>
      <div className="stats-header">
        <p>{caption}</p>
        <div className="row-actions">
          <div className="stats-presets" role="group" aria-label="Time range presets">
            {STATS_RANGE_OPTIONS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`preset-chip${range === item.value ? ' active' : ''}`}
                onClick={() => setRange(item.value)}
              >
                {item.value}
              </button>
            ))}
          </div>
          <label style={{ display: 'inline-grid', gap: 4 }}>
            Range
            <select value={range} onChange={(event) => setRange(event.target.value)}>
              {STATS_RANGE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="stats">
        <div className="stat">
          <span>
            Documents <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(entire tenant)</em>
          </span>
          <strong>{documents}</strong>
        </div>
        <div className="stat">
          <span>
            Quarantined <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(awaiting review)</em>
          </span>
          <strong>
            {adminToken
              ? challengesPending == null
                ? '…'
                : challengesPending
              : '—'}
          </strong>
        </div>
        <div className="stat">
          <span>
            Queries allowed <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(in range)</em>
          </span>
          <strong>{adminToken ? (stats?.queries_allowed ?? '…') : '—'}</strong>
        </div>
        <div className="stat">
          <span>
            Queries blocked <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(in range)</em>
          </span>
          <strong>{adminToken ? (stats?.queries_blocked ?? '…') : '—'}</strong>
        </div>
        <div className="stat">
          <span>
            Ingest total <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(in range)</em>
          </span>
          <strong>{adminToken ? (stats?.ingest_total ?? '…') : '—'}</strong>
        </div>
        <div className="stat">
          <span>
            Audit events <em style={{ fontStyle: 'normal', color: 'var(--muted)' }}>(in range)</em>
          </span>
          <strong>{adminToken ? (stats?.audit_events_total ?? '…') : '—'}</strong>
        </div>
      </div>
    </>
  );
}
