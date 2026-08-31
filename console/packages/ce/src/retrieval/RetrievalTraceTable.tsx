import {
  outcomeClass,
  outcomeLabel,
  retrievalReasonLabel,
  sortRetrievalTrace,
  summarizeTrace,
  type RetrievalDecision,
} from './trace';

type RetrievalTraceTableProps = {
  rows: RetrievalDecision[];
  emptyMessage?: string;
};

export function RetrievalTraceSummaryBar({ rows }: { rows: RetrievalDecision[] }) {
  const summary = summarizeTrace(rows);
  if (!summary.candidates) return null;
  return (
    <p className="muted" style={{ marginBottom: 10 }}>
      {summary.candidates} considered · <span className="pill ok">{summary.selected} used</span>
      {summary.excluded_acl ? (
        <>
          {' '}
          <span className="pill bad">
            {summary.excluded_acl} access denied
          </span>
        </>
      ) : null}
      {summary.excluded_quarantine ? (
        <>
          {' '}
          <span className="pill bad">
            {summary.excluded_quarantine} held for review
          </span>
        </>
      ) : null}
      {summary.excluded_low_score ? (
        <>
          {' '}
          <span className="pill warn">
            {summary.excluded_low_score} below score
          </span>
        </>
      ) : null}
      {summary.not_in_top_k ? (
        <>
          {' '}
          <span className="pill warn">
            {summary.not_in_top_k} not in top results
          </span>
        </>
      ) : null}
      {summary.other ? (
        <>
          {' '}
          <span className="pill">{summary.other} other</span>
        </>
      ) : null}
    </p>
  );
}

export function RetrievalTraceTable({
  rows,
  emptyMessage = 'No retrieval trace rows.',
}: RetrievalTraceTableProps) {
  const ordered = sortRetrievalTrace(rows);
  if (!ordered.length) {
    return (
      <tbody>
        <tr>
          <td colSpan={5}>{emptyMessage}</td>
        </tr>
      </tbody>
    );
  }

  return (
    <tbody>
      {ordered.map((row, index) => (
        <tr key={`${row.chunk_id || row.document_id || 'row'}-${index}`}>
          <td>
            <code>{row.document_id || '—'}</code>
          </td>
          <td>{row.title || '—'}</td>
          <td>{row.score == null ? '—' : Number(row.score).toFixed(4)}</td>
          <td>
            <span className={`pill ${outcomeClass(row.outcome)}`}>{outcomeLabel(row.outcome)}</span>
          </td>
          <td>{retrievalReasonLabel(row.detail)}</td>
        </tr>
      ))}
    </tbody>
  );
}

export function RetrievalTracePanel({
  rows,
  emptyMessage,
}: {
  rows: RetrievalDecision[];
  emptyMessage?: string;
}) {
  return (
    <>
      <RetrievalTraceSummaryBar rows={rows} />
      <div className="table-wrap">
        <table className="claims-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Title</th>
              <th>Score</th>
              <th>Outcome</th>
              <th>Reason</th>
            </tr>
          </thead>
          <RetrievalTraceTable rows={rows} emptyMessage={emptyMessage} />
        </table>
      </div>
    </>
  );
}
