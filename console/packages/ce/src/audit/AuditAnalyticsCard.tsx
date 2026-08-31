import { useEffect, useState } from 'react';

import { ApiError, useAuth, useStatsRange, useToast } from '@rag-protection/console-core';

import { useRefresh } from '../refresh/RefreshContext';
import { AuditBreakdownPanels } from './AuditBreakdownPanels';
import { AuditDecisionChart } from './AuditDecisionChart';
import { AuditHistoryBanner } from './AuditHistoryBanner';
import { chartBucketSeconds, decisionLabel, fmtChartColTitle, fmtCount } from './format';
import type { AuditDrilldown, AuditStatsResponse } from './types';

type AuditAnalyticsCardProps = {
  active: boolean;
  drilldown: AuditDrilldown | null;
  onDrilldown: (next: AuditDrilldown | null) => void;
};

export function AuditAnalyticsCard({ active, drilldown, onDrilldown }: AuditAnalyticsCardProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { toast } = useToast();
  const { window, getWindow } = useStatsRange();
  const { tick, bump } = useRefresh();
  const [bucket, setBucket] = useState('1h');
  const [stats, setStats] = useState<AuditStatsResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!active) return;
    if (!adminToken) {
      setStats(null);
      setError('');
      return;
    }

    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      const win = getWindow();
      try {
        const body = await api.fetchJson<AuditStatsResponse>(
          tenantQuery(
            `/admin/audit/stats?from_ts=${win.from_ts}&to_ts=${win.to_ts}&bucket=${encodeURIComponent(bucket)}`,
          ),
          adminFetchInit(),
        );
        if (cancelled) return;
        setStats(body);
      } catch (err: unknown) {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
        setStats(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [active, adminFetchInit, adminToken, api, bucket, getWindow, tenantQuery, tick]);

  function handleDrilldown(bucketStart: number, decision: '' | 'allow' | 'challenge' | 'block') {
    const bucketSeconds = chartBucketSeconds(bucket);
    const entry =
      (stats?.series || []).find((row) => Number(row.bucket_start) === bucketStart) ||
      { bucket_start: bucketStart };
    const label = fmtChartColTitle(entry, bucket);
    onDrilldown({
      from_ts: bucketStart,
      to_ts: bucketStart + bucketSeconds,
      label,
      decision: decision || undefined,
    });
    toast(
      decision
        ? `Filtered events for ${decisionLabel(decision)} in ${label}`
        : `Filtered events for ${label}`,
    );
  }

  const byDecision = stats?.by_decision || {};
  const summary = adminToken
    ? stats
      ? `${fmtCount(stats.total_events || 0)} events (${window.label}) · ${fmtCount(byDecision.allow || 0)} allowed · ${fmtCount(byDecision.challenge || 0)} challenged · ${fmtCount(byDecision.block || 0)} blocked`
      : loading
        ? 'Loading…'
        : error || 'Failed to load audit stats.'
    : 'Sign in with an admin token to load activity.';

  return (
    <div className="card">
      <h2>Audit activity</h2>
      <p>
        Allowed, challenged, and blocked counts over time. <strong>Click a colored bar</strong> in the
        chart below to filter the event list by that time period. (Table column headers are labels only —
        not clickable.)
      </p>
      <AuditHistoryBanner />
      <div className="row-actions" style={{ marginBottom: 14 }}>
        <label style={{ display: 'inline-grid', gap: 4 }}>
          Group by
          <select value={bucket} onChange={(event) => setBucket(event.target.value)}>
            <option value="5m">5 minutes</option>
            <option value="1h">1 hour</option>
            <option value="1d">1 day</option>
          </select>
        </label>
        <button type="button" onClick={bump}>
          Refresh
        </button>
      </div>
      {drilldown ? (
        <p className="audit-drilldown-hint">
          Chart filter: {drilldown.label}
          {drilldown.decision ? ` · ${decisionLabel(drilldown.decision)}` : ''}.{' '}
          <button type="button" onClick={() => onDrilldown(null)}>
            Clear chart filter
          </button>
        </p>
      ) : null}
      <div style={{ marginBottom: 12, color: 'var(--muted)', fontSize: 13 }}>{summary}</div>
      {adminToken && stats ? (
        <>
          <AuditDecisionChart
            series={stats.series || []}
            bucket={bucket}
            onDrilldown={handleDrilldown}
          />
          <div className="chart-legend">
            <span className="allow">Allowed</span>
            <span className="challenge">Challenged</span>
            <span className="block">Blocked</span>
          </div>
          <p className="audit-chart-interaction-hint">
            Click any colored bar (or empty slot above a date label) to filter events below. Scroll
            horizontally if the range has many time periods.
          </p>
          <AuditBreakdownPanels byKind={stats.by_kind} byScanner={stats.by_scanner} />
        </>
      ) : null}
    </div>
  );
}
