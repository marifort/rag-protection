import { RetrievalTracePanel } from '../retrieval/RetrievalTraceTable';
import { parseRetrievalTraceDetail } from '../retrieval/trace';
import type { CitationClaimAuditRow } from './citationDetail';
import { parseCitationAuditDetail } from './citationDetail';
import type { AuditEvent } from './types';
import {
  auditKindLabel,
  auditWhereLabel,
  decisionLabel,
  formatAuditEventDetail,
  formatFindingSummary,
  formatRiskScore,
  fmtTs,
  hasAuditDebug,
  hasDebugContent,
  renderDebugHint,
  scannerLabel,
  findingCategoryLabel,
} from './format';

type AuditEventDrawerProps = {
  row: AuditEvent | null;
  onClose: () => void;
};

function FindingsTable({ findings }: { findings: AuditEvent['findings'] }) {
  const rows = Array.isArray(findings) ? findings : [];
  if (!rows.length) {
    return <p style={{ margin: 0, color: 'var(--muted)', fontSize: 12 }}>No findings recorded.</p>;
  }
  return (
    <table className="audit-findings-table">
      <thead>
        <tr>
          <th>Detector</th>
          <th>Category</th>
          <th>Label</th>
          <th>Severity</th>
          <th>Snippet</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((finding, index) => (
          <tr key={`${finding.scanner}-${finding.label}-${index}`}>
            <td>{scannerLabel(finding.scanner)}</td>
            <td>{findingCategoryLabel(finding.category) || finding.category}</td>
            <td>{finding.label || '—'}</td>
            <td>{finding.severity ?? ''}</td>
            <td>{finding.snippet || finding.detail || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CitationClaimsTable({ claims }: { claims: CitationClaimAuditRow[] }) {
  if (!claims.length) {
    return <p style={{ margin: 0, color: 'var(--muted)', fontSize: 12 }}>No citation claims recorded.</p>;
  }
  return (
    <table className="audit-findings-table">
      <thead>
        <tr>
          <th>Sentence</th>
          <th>chunk_id</th>
          <th>Supported</th>
          <th>Entailment</th>
        </tr>
      </thead>
      <tbody>
        {claims.map((claim, index) => (
          <tr key={`${claim.chunk_id ?? 'claim'}-${index}`}>
            <td>{claim.sentence || '—'}</td>
            <td>
              <code>{claim.chunk_id || '—'}</code>
            </td>
            <td>
              <span className={`pill ${claim.supported ? 'ok' : 'bad'}`}>{String(!!claim.supported)}</span>
            </td>
            <td>{claim.entailment_score == null ? '—' : String(claim.entailment_score)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CitationAuditSection({ row }: { row: AuditEvent }) {
  const fromDetail =
    row.kind === 'citation_failed' ? parseCitationAuditDetail(row.detail) : null;
  const debugClaims = Array.isArray(row.debug?.citation_claims) ? row.debug.citation_claims : [];
  const claims = fromDetail?.claims?.length
    ? fromDetail.claims
    : fromDetail?.unsupported_claims?.length
      ? fromDetail.unsupported_claims
      : debugClaims;
  if (!claims.length && !fromDetail) return null;

  const coverage =
    fromDetail?.coverage_ratio ??
    (typeof row.debug?.citation_coverage_ratio === 'number' ? row.debug.citation_coverage_ratio : null);

  return (
    <section className="audit-drawer-section">
      <h4>Citation claims {fromDetail ? '(detail)' : '(debug)'}</h4>
      <p style={{ margin: '0 0 10px', color: 'var(--muted)', fontSize: 12 }}>
        {fromDetail?.summary || 'Per-claim grounding from citation check'}
        {coverage != null ? ` · coverage ${Number(coverage).toFixed(2)}` : ''}
        {fromDetail?.unsupported_count != null ? ` · unsupported ${fromDetail.unsupported_count}` : ''}
        {fromDetail?.hard_gate_failed ? ' · hard gate failed' : ''}
      </p>
      <CitationClaimsTable claims={claims} />
    </section>
  );
}

function RetrievalTraceSection({ row }: { row: AuditEvent }) {
  if (row.kind !== 'retrieval_trace') return null;
  const parsed = parseRetrievalTraceDetail(row.detail);
  if (!parsed) {
    return (
      <section className="audit-drawer-section">
        <h4>Retrieval</h4>
        <p style={{ margin: 0, color: 'var(--muted)', fontSize: 12 }}>
          Could not read retrieval details for this event.
        </p>
      </section>
    );
  }
  return (
    <section className="audit-drawer-section">
      <h4>Why this was retrieved</h4>
      <p style={{ margin: '0 0 10px', color: 'var(--muted)', fontSize: 12 }}>
        {parsed.candidates ?? parsed.trace.length} passages considered · {parsed.selected ?? '—'} used.
        The table shows why each candidate was kept or dropped. Audit keeps up to 50 rows.
      </p>
      <RetrievalTracePanel
        rows={parsed.trace}
        emptyMessage="No trace rows in this audit event."
      />
    </section>
  );
}

function DebugSection({ row }: { row: AuditEvent }) {
  const debug = row.debug;
  if (!hasDebugContent(debug)) {
    return (
      <p style={{ margin: 0, color: 'var(--muted)', fontSize: 12 }}>
        {renderDebugHint(row.kind, row.source)}
      </p>
    );
  }
  const chunks =
    Array.isArray(debug?.chunk_ids) && debug.chunk_ids.length ? debug.chunk_ids.join(', ') : '—';
  return (
    <>
      {debug?.query_preview ? (
        <div>
          <h4>Query preview</h4>
          <pre className="audit-drawer-pre">{debug.query_preview}</pre>
        </div>
      ) : null}
      {debug?.input_preview ? (
        <div>
          <h4>Input preview</h4>
          <pre className="audit-drawer-pre">{debug.input_preview}</pre>
        </div>
      ) : null}
      {debug?.output_preview ? (
        <div>
          <h4>Output preview</h4>
          <pre className="audit-drawer-pre">{debug.output_preview}</pre>
        </div>
      ) : null}
      <dl className="audit-drawer-meta">
        <dt>Redactions</dt>
        <dd>{debug?.redactions ?? '—'}</dd>
        <dt>Chunk IDs</dt>
        <dd>{chunks}</dd>
        {debug?.citation_coverage_ratio != null ? (
          <>
            <dt>Citation coverage</dt>
            <dd>{Number(debug.citation_coverage_ratio).toFixed(2)}</dd>
          </>
        ) : null}
      </dl>
    </>
  );
}

export function AuditEventDrawer({ row, onClose }: AuditEventDrawerProps) {
  if (!row) return null;

  return (
    <>
      <div className="audit-drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="audit-drawer" aria-hidden="false">
        <div className="audit-drawer-header">
          <h3>
            {auditKindLabel(row.kind) || 'Event'} · {decisionLabel(row.decision)}
          </h3>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="audit-drawer-body">
          <section className="audit-drawer-section">
            <h4>Summary</h4>
            <dl className="audit-drawer-meta">
              <dt>Time</dt>
              <dd>{fmtTs(row.timestamp)}</dd>
              <dt>Type</dt>
              <dd>{auditKindLabel(row.kind) || '—'}</dd>
              <dt>Where</dt>
              <dd>{auditWhereLabel(row.source) || '—'}</dd>
              <dt>Decision</dt>
              <dd>{decisionLabel(row.decision) || '—'}</dd>
              <dt>Risk</dt>
              <dd>{formatRiskScore(row.risk_score)}</dd>
              <dt>User</dt>
              <dd>{row.subject || '—'}</dd>
              <dt>Source</dt>
              <dd>{row.source || '—'}</dd>
              <dt>Detail</dt>
              <dd>{formatAuditEventDetail(row.kind, row.detail) || '—'}</dd>
              <dt>Findings</dt>
              <dd>{formatFindingSummary(row.findings) || '—'}</dd>
            </dl>
          </section>
          <section className="audit-drawer-section">
            <h4>Findings</h4>
            <FindingsTable findings={row.findings} />
          </section>
          <CitationAuditSection row={row} />
          <RetrievalTraceSection row={row} />
          <section className="audit-drawer-section">
            <h4>Debug previews</h4>
            <DebugSection row={row} />
            {hasAuditDebug(row) ? <span className="pill debug">debug</span> : null}
          </section>
        </div>
      </aside>
    </>
  );
}
