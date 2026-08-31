import { useLayoutEffect, useMemo, useRef, useState } from 'react';

import type { AuditStatsBucket } from './types';
import {
  AUDIT_CHART_COL_GAP,
  chartTickBudget,
  columnWidth,
  computeBarScale,
  fmtChartBucketLabel,
  fmtChartColTitle,
  fmtCount,
  pickChartTickIndexes,
  plotWidth,
  trimAuditChartSeries,
} from './format';

type AuditDecisionChartProps = {
  series: AuditStatsBucket[];
  bucket: string;
  onDrilldown: (bucketStart: number, decision: '' | 'allow' | 'challenge' | 'block') => void;
};

export function AuditDecisionChart({ series, bucket, onDrilldown }: AuditDecisionChartProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState(0);
  const trimmed = useMemo(() => trimAuditChartSeries(series), [series]);
  const colWidth = columnWidth(trimmed.length, viewport);
  const width = plotWidth(trimmed.length, colWidth);
  const step = colWidth + AUDIT_CHART_COL_GAP;
  const tickIndexes = pickChartTickIndexes(trimmed.length, chartTickBudget(Math.max(width, viewport)));

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const measure = () => {
      setViewport(el.clientWidth);
    };
    measure();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [trimmed.length]);

  useLayoutEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollLeft = 0;
  }, [trimmed, bucket]);

  if (!trimmed.length) {
    return <p style={{ color: 'var(--muted)', margin: 0, padding: '8px 0' }}>No audit events in selected range.</p>;
  }

  const maxTotal = Math.max(
    1,
    ...trimmed.map((entry) => (entry.allow || 0) + (entry.challenge || 0) + (entry.block || 0)),
  );
  const scale = computeBarScale(maxTotal);
  const axisWidth = Math.max(width, viewport || 0) || undefined;

  return (
    <div className="audit-timeseries-panel">
      <div className="audit-chart-frame">
        <div className="audit-chart-y-axis">
          {scale.ticks
            .slice()
            .reverse()
            .map((tick) => (
              <span key={tick}>{fmtCount(tick)}</span>
            ))}
        </div>
        <div className="audit-chart-scroll" ref={scrollRef}>
          <div className="audit-chart-plot" style={{ width: axisWidth, minWidth: '100%' }}>
            <div
              className="chart-stack"
              style={{
                gridTemplateColumns: `repeat(${trimmed.length}, ${colWidth}px)`,
                gap: AUDIT_CHART_COL_GAP,
                ['--audit-chart-col-width' as string]: `${colWidth}px`,
              }}
            >
              {trimmed.map((entry, index) => {
                const allow = entry.allow || 0;
                const challenge = entry.challenge || 0;
                const block = entry.block || 0;
                const allowH = scale.scaleMax ? (allow / scale.scaleMax) * 100 : 0;
                const challengeH = scale.scaleMax ? (challenge / scale.scaleMax) * 100 : 0;
                const blockH = scale.scaleMax ? (block / scale.scaleMax) * 100 : 0;
                const bucketTs = Number(entry.bucket_start);
                const title = fmtChartColTitle(entry, bucket);

                const seg = (cls: 'allow' | 'challenge' | 'block', count: number, height: number) =>
                  count > 0 ? (
                    <div
                      key={cls}
                      className={`chart-seg ${cls}`}
                      style={{ height: `${height}%` }}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDrilldown(bucketTs, cls);
                      }}
                    />
                  ) : null;

                return (
                  <div
                    key={`${bucketTs}-${index}`}
                    className="chart-col"
                    role="button"
                    tabIndex={0}
                    title={`${title} — click to filter events`}
                    onClick={() => onDrilldown(bucketTs, '')}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onDrilldown(bucketTs, '');
                      }
                    }}
                  >
                    {seg('block', block, blockH)}
                    {seg('challenge', challenge, challengeH)}
                    {seg('allow', allow, allowH)}
                  </div>
                );
              })}
            </div>
            <div className="audit-chart-x-axis" style={{ width: axisWidth }}>
              {tickIndexes.map((index, tickPos) => {
                const entry = trimmed[index];
                const left = index * step + colWidth / 2;
                const prevTick = tickPos > 0 ? tickIndexes[tickPos - 1] : undefined;
                const prev =
                  prevTick != null
                    ? new Date((trimmed[prevTick].bucket_start || 0) * 1000)
                    : null;
                const label = fmtChartBucketLabel(entry.bucket_start, bucket, {
                  prevDay: prev,
                  isFirst: tickPos === 0,
                });
                return (
                  <span key={index} className="audit-chart-x-tick" style={{ left }}>
                    {label.line2 ? (
                      <span className="audit-chart-x-tick-lines">
                        <span>{label.line1}</span>
                        <span>{label.line2}</span>
                      </span>
                    ) : (
                      label.line1
                    )}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
