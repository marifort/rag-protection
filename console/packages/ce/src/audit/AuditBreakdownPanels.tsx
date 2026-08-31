import { auditKindLabel, computeBarScale, scannerLabel } from './format';

const ROWS = 8;

type AuditBreakdownPanelsProps = {
  byKind?: Record<string, number>;
  byScanner?: Record<string, number>;
};

function padEntries(entries: Array<[string, number] | null>, rowCount: number) {
  const out = entries.slice();
  while (out.length < rowCount) out.push(null);
  return out;
}

function BreakdownCell({
  entry,
  scaleMax,
  formatLabel,
}: {
  entry: [string, number] | null;
  scaleMax: number;
  formatLabel: (value: string) => string;
}) {
  if (!entry) return <div className="breakdown-cell breakdown-cell-empty" aria-hidden="true" />;
  const [label, value] = entry;
  const pct = scaleMax ? Math.min(100, (value / scaleMax) * 100) : 0;
  return (
    <div className="breakdown-cell">
      <span className="bar-label">{formatLabel(label)}</span>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${value ? Math.max(2, pct) : 0}%` }} />
      </div>
      <span className="bar-value">{value}</span>
    </div>
  );
}

function BreakdownMeter({ scaleMax, ticks }: { scaleMax: number; ticks: number[] }) {
  return (
    <div className="breakdown-meter">
      <span aria-hidden="true" />
      <div className="breakdown-meter-axis">
        <div className="breakdown-meter-track">
          {ticks.map((tick, index) => (
            <span
              key={tick}
              className="breakdown-meter-tick"
              style={index === 0 ? undefined : { left: `${scaleMax ? (tick / scaleMax) * 100 : 0}%` }}
            >
              {tick}
            </span>
          ))}
        </div>
        <div className="breakdown-meter-label">Events</div>
      </div>
      <span aria-hidden="true" />
    </div>
  );
}

export function AuditBreakdownPanels({ byKind, byScanner }: AuditBreakdownPanelsProps) {
  const kindEntries = Object.entries(byKind || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, ROWS) as Array<[string, number]>;
  const scannerEntries = Object.entries(byScanner || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, ROWS) as Array<[string, number]>;

  const kindMax = kindEntries.length ? Math.max(...kindEntries.map((entry) => entry[1]), 0) : 0;
  const scannerMax = scannerEntries.length ? Math.max(...scannerEntries.map((entry) => entry[1]), 0) : 0;
  const scale = computeBarScale(Math.max(kindMax, scannerMax));
  const kindRows = padEntries(kindEntries, ROWS);
  const scannerRows = padEntries(scannerEntries, ROWS);

  if (!kindEntries.length && !scannerEntries.length) {
    return <p className="muted" style={{ margin: 0 }}>No breakdown data for the selected range.</p>;
  }

  return (
    <div className="breakdown-duo">
      <h3 className="breakdown-duo-head">By event type</h3>
      <h3 className="breakdown-duo-head">By detector</h3>
      {kindRows.map((kindEntry, index) => (
        <div key={`row-${index}`} className="breakdown-duo-row">
          <BreakdownCell entry={kindEntry} scaleMax={scale.scaleMax} formatLabel={auditKindLabel} />
          <BreakdownCell entry={scannerRows[index]} scaleMax={scale.scaleMax} formatLabel={scannerLabel} />
        </div>
      ))}
      <div className="breakdown-duo-meter">
        <BreakdownMeter scaleMax={scale.scaleMax} ticks={scale.ticks} />
      </div>
      <div className="breakdown-duo-meter">
        <BreakdownMeter scaleMax={scale.scaleMax} ticks={scale.ticks} />
      </div>
    </div>
  );
}
