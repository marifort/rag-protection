import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  useAuth,
  useToast,
  useWorkspaceNav,
  type WorkspaceComponentProps,
} from '@rag-protection/console-core';

import { useRefresh } from '../refresh/RefreshContext';
import type { ToolPolicyEntryView, ToolPolicyResponse } from '../tools/types';

type ToolChallengeRow = {
  id: string;
  tool: string;
  subject?: string;
  groups?: string[];
  risk_score?: number;
  reason?: string;
  findings?: Array<{ scanner?: string; category?: string; severity?: number }>;
  created_at?: number;
  arguments?: Record<string, unknown>;
};

type ToolChallengeListResponse = {
  count?: number;
  challenges?: ToolChallengeRow[];
  tool_challenge_mode?: string;
  tenant_id?: string;
};

function listLabel(values?: string[]) {
  if (!Array.isArray(values) || !values.length) return '—';
  return values.join(', ');
}

function formatArguments(args?: Record<string, unknown>): string {
  if (!args || !Object.keys(args).length) return '—';
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

function toolRows(body: ToolPolicyResponse | null): Array<ToolPolicyEntryView & { name: string }> {
  if (!body?.tools) return [];
  return Object.entries(body.tools).map(([name, entry]) => ({
    ...entry,
    name: entry.name || name,
  }));
}

function findingChips(row: ToolChallengeRow) {
  const scanners = new Set<string>();
  const categories = new Set<string>();
  for (const finding of row.findings || []) {
    if (finding.scanner) scanners.add(finding.scanner);
    if (finding.category) categories.add(finding.category);
  }
  return {
    scanners: Array.from(scanners),
    categories: Array.from(categories),
  };
}

export function ToolGatewayPane({ active, refreshTick = 0 }: WorkspaceComponentProps) {
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { navigateTo } = useWorkspaceNav();
  const { toast } = useToast();
  const { tick } = useRefresh();
  const [policy, setPolicy] = useState<ToolPolicyResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [challenges, setChallenges] = useState<ToolChallengeRow[]>([]);
  const [challengeMode, setChallengeMode] = useState('');
  const [challengeError, setChallengeError] = useState('');
  const [challengeLoading, setChallengeLoading] = useState(false);
  const [actingId, setActingId] = useState('');
  const [queueTick, setQueueTick] = useState(0);

  const loadPolicy = useCallback(
    async (opts?: { silent?: boolean }) => {
      const silent = !!opts?.silent;
      if (!adminToken.trim()) {
        setPolicy(null);
        setError('');
        return;
      }
      if (!silent) setLoading(true);
      try {
        const body = await api.fetchJson<ToolPolicyResponse>('/admin/tools/policy', adminFetchInit());
        setPolicy((prev) => (JSON.stringify(prev) === JSON.stringify(body) ? prev : body));
        setError('');
      } catch (err) {
        if (!silent) setPolicy(null);
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [adminFetchInit, adminToken, api],
  );

  const loadChallenges = useCallback(
    async (opts?: { silent?: boolean }) => {
      const silent = !!opts?.silent;
      if (!adminToken.trim()) {
        setChallenges([]);
        setChallengeMode('');
        setChallengeError('');
        return;
      }
      if (!silent) setChallengeLoading(true);
      try {
        const body = await api.fetchJson<ToolChallengeListResponse>(
          tenantQuery('/admin/tools/challenges'),
          adminFetchInit(),
        );
        setChallenges(Array.isArray(body.challenges) ? body.challenges : []);
        setChallengeMode(String(body.tool_challenge_mode || ''));
        setChallengeError('');
      } catch (err) {
        if (!silent) setChallenges([]);
        setChallengeError(err instanceof ApiError ? err.message : String(err));
      } finally {
        if (!silent) setChallengeLoading(false);
      }
    },
    [adminFetchInit, adminToken, api, tenantQuery],
  );

  useEffect(() => {
    if (!active) return;
    void loadPolicy({ silent: false });
    void loadChallenges({ silent: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, adminToken]);

  useEffect(() => {
    if (!active || !adminToken.trim()) return;
    void loadPolicy({ silent: true });
    void loadChallenges({ silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, adminToken, refreshTick, tick, queueTick]);

  async function actOnChallenge(id: string, action: 'approve' | 'deny') {
    if (!adminToken.trim() || actingId) return;
    if (action === 'deny' && !window.confirm('Deny this tool invoke? The backend will never run.')) {
      return;
    }
    setActingId(id);
    setChallengeError('');
    try {
      await api.fetchJson(tenantQuery(`/admin/tools/challenges/${encodeURIComponent(id)}/${action}`), {
        ...adminFetchInit(),
        method: 'POST',
        headers: {
          ...(adminFetchInit().headers as Record<string, string>),
          'Content-Type': 'application/json',
        },
        body: action === 'deny' ? JSON.stringify({ reason: 'Denied from Tool Gateway' }) : undefined,
      });
      toast(action === 'approve' ? 'Tool invoke approved and executed.' : 'Tool invoke denied.');
      setQueueTick((n) => n + 1);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setChallengeError(message);
      toast(message, 'err');
    } finally {
      setActingId('');
    }
  }

  if (!active) return null;

  const rows = toolRows(policy);
  const defaults = policy?.defaults || {};
  const mode = challengeMode || defaults.challenge_mode || '';
  const modeBlocksQueue = mode === 'block' || mode === 'audit_only';

  return (
    <>
      <div className="card">
        <h2>Tool Gateway</h2>
        <p>
          Tool policy and reload. Mid-risk invokes can wait in the review queue when challenge mode is
          allow. Outcomes appear in Audit Log.
        </p>
        {!adminToken.trim() ? (
          <p className="muted">Set admin bearer token in the toolbar (needs <code>policy_admin</code>).</p>
        ) : null}
        <div className="row-actions" style={{ marginBottom: 12 }}>
          <button
            type="button"
            disabled={loading || !adminToken.trim()}
            onClick={() => {
              void loadPolicy({ silent: false });
              void loadChallenges({ silent: false });
            }}
          >
            {loading || challengeLoading ? 'Refreshing…' : 'Refresh tool policy'}
          </button>
          <button
            type="button"
            className="primary"
            disabled={!adminToken.trim()}
            onClick={() => navigateTo('audit', { type: 'filter-kind', kind: 'tool_invoke' })}
          >
            View tool calls in Audit
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <dl className="meta-kv" style={{ marginBottom: 14 }}>
          <dt>source_path</dt>
          <dd>
            <code>{policy?.source_path || (loading ? '…' : '—')}</code>
          </dd>
          <dt>tool_count</dt>
          <dd>{policy?.tool_count ?? (loading ? '…' : 0)}</dd>
          <dt>challenge_mode</dt>
          <dd>
            <span className="pill">{mode || '—'}</span>
          </dd>
          <dt>challenge_threshold</dt>
          <dd>{defaults.challenge_threshold ?? '—'}</dd>
          <dt>block_threshold</dt>
          <dd>{defaults.block_threshold ?? '—'}</dd>
        </dl>
      </div>

      <div className="card" data-testid="tool-challenge-queue">
        <h2>
          Review queue
          {challenges.length ? (
            <span className="pill warn" style={{ marginLeft: 8 }}>
              {challenges.length} pending
            </span>
          ) : null}
        </h2>
        <p>
          Mid-risk tool calls waiting for human approval.{' '}
          <strong>Approve</strong> runs the tool once; <strong>Deny</strong> never runs it.
        </p>
        {modeBlocksQueue ? (
          <p className="dlp-hint" style={{ marginBottom: 10 }}>
            Review queue is off — challenge mode is <code>{mode || 'block'}</code>. Set it to{' '}
            <code>allow</code> in the tool policy and reload so mid-risk calls enter this queue.
          </p>
        ) : null}
        {challengeError ? <p className="error-text">{challengeError}</p> : null}
        {!adminToken.trim() ? (
          <p className="muted">Set admin bearer token to load pending tool invokes.</p>
        ) : challenges.length ? (
          <div className="table-wrap">
            <table className="audit-findings-table">
              <thead>
                <tr>
                  {['Tool', 'Caller', 'Risk', 'Findings', 'Arguments', 'Reason', 'Actions'].map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {challenges.map((row) => {
                  const { scanners, categories } = findingChips(row);
                  const argsText = formatArguments(row.arguments);
                  return (
                    <tr key={row.id}>
                      <td>
                        <code>{row.tool}</code>
                      </td>
                      <td>
                        <code>{row.subject || '—'}</code>
                        <div className="muted" style={{ fontSize: 11 }}>
                          {listLabel(row.groups)}
                        </div>
                      </td>
                      <td>{typeof row.risk_score === 'number' ? row.risk_score.toFixed(2) : '—'}</td>
                      <td>
                        <div className="row-actions" style={{ flexWrap: 'wrap', gap: 6 }}>
                          <span className="pill warn">challenge</span>
                          {scanners.map((scanner) => (
                            <span key={scanner} className="pill">
                              {scanner}
                            </span>
                          ))}
                          {categories.map((category) => (
                            <span key={category} className="pill bad">
                              {category}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <pre
                          data-testid={`tool-challenge-args-${row.id}`}
                          style={{
                            margin: 0,
                            maxWidth: 320,
                            maxHeight: 120,
                            overflow: 'auto',
                            fontSize: 11,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {argsText}
                        </pre>
                      </td>
                      <td>
                        <span className="muted" style={{ fontSize: 12 }}>
                          {row.reason || '—'}
                        </span>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            type="button"
                            className="primary"
                            disabled={!!actingId}
                            onClick={() => void actOnChallenge(row.id, 'approve')}
                          >
                            {actingId === row.id ? '…' : 'Approve'}
                          </button>
                          <button
                            type="button"
                            disabled={!!actingId}
                            onClick={() => void actOnChallenge(row.id, 'deny')}
                          >
                            Deny
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="dlp-hint" style={{ margin: 0 }}>
            {challengeLoading
              ? 'Loading review queue…'
              : modeBlocksQueue
                ? 'Nothing waiting (review queue is off).'
                : 'Queue is empty — mid-risk tool calls will appear here.'}
          </p>
        )}
        <div className="row-actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            disabled={!adminToken.trim()}
            onClick={() => navigateTo('audit', { type: 'filter-kind', kind: 'tool_challenge_approved' })}
          >
            View approved in Audit
          </button>
          <button
            type="button"
            disabled={!adminToken.trim()}
            onClick={() => navigateTo('audit', { type: 'filter-kind', kind: 'tool_challenge_denied' })}
          >
            View denied in Audit
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Registered tools</h2>
        <p>
          Which groups may call each tool, and which patterns or domains are blocked. Poisoned-tool scan
          results appear when a description is blocked.
        </p>
        {rows.length ? (
          <div className="table-wrap">
            <table className="audit-findings-table">
              <thead>
                <tr>
                  {[
                    'Tool',
                    'Backend',
                    'Allowed groups',
                    'Blocked patterns',
                    'Blocked domains',
                    'Desc blocked',
                    'Scan args',
                  ].map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.name}
                    className={row.description_blocked ? 'claim-unsupported' : undefined}
                  >
                    <td>
                      <code>{row.name}</code>
                      {row.mcp_tool ? (
                        <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                          mcp: {row.mcp_tool}
                        </div>
                      ) : null}
                    </td>
                    <td>{row.backend || '—'}</td>
                    <td>{listLabel(row.allowed_groups)}</td>
                    <td>{listLabel(row.blocked_patterns)}</td>
                    <td>{listLabel(row.blocked_domains)}</td>
                    <td>
                      <span className={`pill ${row.description_blocked ? 'bad' : 'ok'}`}>
                        {String(!!row.description_blocked)}
                      </span>
                      {row.description_findings_count ? (
                        <span className="muted" style={{ marginLeft: 6 }}>
                          ({row.description_findings_count})
                        </span>
                      ) : null}
                    </td>
                    <td>{listLabel(row.scan_arguments)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="dlp-hint" style={{ margin: 0 }}>
            {adminToken.trim()
              ? loading
                ? 'Loading tool policy…'
                : 'No tools registered — check RAG_TOOL_POLICY_FILE / tool_policy.yaml.'
              : 'Set admin bearer token to load tool policy.'}
          </p>
        )}
        <p className="dlp-hint" style={{ marginTop: 12 }}>
          With Enterprise, Tool Gateway also offers register, edit, and retire.
        </p>
      </div>
    </>
  );
}
