import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderCePane } from '../test/renderPane';
import { AuditLogPane } from './AuditLogPane';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockAuditFetch(overrides?: {
  integrity?: Record<string, unknown>;
  withExfilPair?: boolean;
  statsSeries?: Array<Record<string, unknown>>;
  events?: Array<Record<string, unknown>>;
}) {
  const withExfilPair = overrides?.withExfilPair ?? false;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = String(url);
      if (path.includes('/admin/auth/me')) {
        return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: ['audit_reader'] }) });
      }
      if (path.includes('/admin/audit/integrity/verify')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify(
              overrides?.integrity ?? {
                valid: true,
                events_checked: 42,
                error: null,
                integrity_chain_enabled: true,
                audit_file: '/data/audit.jsonl',
              },
            ),
        });
      }
      if (path.includes('/admin/audit/export')) {
        return Promise.resolve({
          ok: true,
          blob: async () => new Blob(['{}'], { type: 'application/jsonl' }),
        });
      }
      if (path.includes('/admin/audit/stats')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              total_events: overrides?.statsSeries ? 3 : 0,
              series: overrides?.statsSeries ?? [],
            }),
        });
      }
      if (path.includes('kind=extraction_suspected')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              events: withExfilPair
                ? [
                    {
                      kind: 'extraction_suspected',
                      subject: 'alice.engineer',
                      tenant_id: 'default',
                      timestamp: 1_752_048_000,
                    },
                  ]
                : [],
              total: withExfilPair ? 1 : 0,
            }),
        });
      }
      if (path.includes('kind=canary_triggered')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              events: withExfilPair
                ? [
                    {
                      kind: 'canary_triggered',
                      subject: 'alice.engineer',
                      tenant_id: 'default',
                      timestamp: 1_752_048_100,
                    },
                  ]
                : [],
              total: withExfilPair ? 1 : 0,
            }),
        });
      }
      if (path.includes('/admin/audit/events')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              events: overrides?.events ?? [],
              total: (overrides?.events ?? []).length,
            }),
        });
      }
      if (path.includes('/health')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify({ status: 'healthy', audit: { file_sink: null } }),
        });
      }
      return Promise.resolve({ ok: true, text: async () => '{}' });
    }),
  );
}

describe('AuditLogPane toast notifications', () => {
  it('disables export when admin token is missing', () => {
    renderCePane(AuditLogPane, { adminToken: '', activeWorkspaceId: 'audit' });
    expect(screen.getByRole('button', { name: 'Download export' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Check integrity' })).toBeDisabled();
  });

  it('clears decision filter when clearing chart drill-down', async () => {
    mockAuditFetch({
      statsSeries: [{ bucket_start: 1_752_048_000, allow: 0, challenge: 0, block: 3, total: 3 }],
    });
    const { container } = renderCePane(AuditLogPane, {
      adminToken: 'admin-token',
      activeWorkspaceId: 'audit',
    });

    const blockSeg = await waitFor(() => {
      const seg = container.querySelector('.chart-seg.block');
      expect(seg).toBeTruthy();
      return seg as HTMLElement;
    });
    fireEvent.click(blockSeg);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Decision' })).toHaveValue('block');
    });
    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('decision=block'))).toBe(true);
    });

    const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>;
    const callsBeforeClear = fetchMock.mock.calls.length;
    fireEvent.click(screen.getAllByRole('button', { name: 'Clear chart filter' })[0]);

    expect(screen.getByRole('combobox', { name: 'Decision' })).toHaveValue('');
    await waitFor(() => {
      const newCalls = fetchMock.mock.calls
        .slice(callsBeforeClear)
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/admin/audit/events'));
      expect(newCalls.length).toBeGreaterThan(0);
      expect(newCalls.every((url) => !url.includes('decision='))).toBe(true);
    });
  });

  it('applies tool_invoke kind preset chip', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Tool call' }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('kind=tool_invoke'))).toBe(true);
    });
  });

  it('applies acl_sync kind preset chip', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Access update' }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('kind=acl_sync'))).toBe(true);
    });
  });

  it('applies connector_sync kind preset chip', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Connector sync' }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('kind=connector_sync'))).toBe(true);
    });
  });

  it('applies retrieved-document where chip with input scan', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Retrieved document' }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('kind=scan_input') && url.includes('where=document'))).toBe(true);
    });
  });

  it('applies answer where chip with answer scan', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Answer' }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('kind=scan_output') && url.includes('where=output'))).toBe(true);
    });
  });

  it('shows Query vs Retrieved document in the Where column', async () => {
    mockAuditFetch({
      events: [
        {
          kind: 'scan_input',
          source: 'rag:user_query',
          subject: 'alice.engineer',
          timestamp: 1_752_048_000,
          decision: 'allow',
          findings: [{ category: 'ssn' }],
        },
        {
          kind: 'scan_input',
          source: 'rag:chunk:chunk-1',
          subject: 'alice.engineer',
          timestamp: 1_752_048_001,
          decision: 'allow',
          findings: [{ category: 'ssn' }],
        },
      ],
    });
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    expect(await screen.findByRole('columnheader', { name: 'Where' })).toBeInTheDocument();
    expect(await screen.findByRole('cell', { name: 'Query' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Retrieved document' })).toBeInTheDocument();
  });

  it('shows risk scores to two decimals instead of float noise', async () => {
    mockAuditFetch({
      events: [
        {
          kind: 'scan_input',
          source: 'rag:user_query',
          subject: 'bob.hr',
          timestamp: 1_752_048_000,
          decision: 'block',
          risk_score: 0.799999999,
        },
      ],
    });
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    expect(await screen.findByRole('cell', { name: '0.79' })).toBeInTheDocument();
    expect(screen.queryByText(/0\.799999/)).not.toBeInTheDocument();
  });

  it('summarizes retrieval trace JSON in the Detail column', async () => {
    mockAuditFetch({
      events: [
        {
          kind: 'retrieval_trace',
          source: 'retrieval.explain',
          subject: 'alice.engineer',
          timestamp: 1_752_048_000,
          decision: 'allow',
          detail: JSON.stringify({
            candidates: 42,
            selected: 4,
            trace: [
              { outcome: 'selected', title: 'Engineering incident runbook-7' },
              { outcome: 'excluded_low_score', title: 'Zephyr Phantom Ledger' },
            ],
          }),
        },
      ],
    });
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    expect(await screen.findByText('click Detail', { selector: '.audit-detail-click-hint' })).toBeInTheDocument();
    expect(screen.getByText(/4 used of 42 considered · 1 below score/)).toBeInTheDocument();
    expect(screen.getByText('click Detail', { selector: '.audit-detail-click-hint' })).toHaveClass(
      'audit-detail-click-hint',
    );
    expect(screen.queryByText(/query_len/)).not.toBeInTheDocument();
  });

  it('renders Exfil correlation strip on Audit Log', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });
    expect(await screen.findByRole('heading', { name: 'Suspected data theft' })).toBeInTheDocument();
    expect(screen.getByText('0 pairs')).toBeInTheDocument();
  });

  it('Filter table applies subject search for an exfil pair', async () => {
    mockAuditFetch({ withExfilPair: true });
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    expect(await screen.findByText('alice.engineer')).toBeInTheDocument();
    expect(screen.getByText('1 high-confidence')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Filter table' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(
        'Filtered events to alice.engineer',
      );
    });
    expect(screen.getByPlaceholderText('user, detail, labels…')).toHaveValue('alice.engineer');
    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
      expect(calls.some((url) => url.includes('search=alice.engineer'))).toBe(true);
    });
  });

  it('shows a success toast after audit export completes', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Download export' }));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Audit export downloaded.'),
    );
  });

  it('verifies the integrity chain and shows valid + entry count', async () => {
    mockAuditFetch();
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    expect(screen.getByRole('heading', { name: 'Log integrity' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check integrity' }));

    await waitFor(() => {
      expect(screen.getAllByText('Valid · 42 events checked').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('/data/audit.jsonl')).toBeInTheDocument();
  });

  it('shows not configured instead of invalid when no audit file is set', async () => {
    mockAuditFetch({
      integrity: {
        valid: false,
        events_checked: 0,
        error: 'no audit file configured',
        integrity_chain_enabled: true,
      },
    });
    renderCePane(AuditLogPane, { adminToken: 'admin-token', activeWorkspaceId: 'audit' });

    fireEvent.click(screen.getByRole('button', { name: 'Check integrity' }));

    await waitFor(() => {
      expect(screen.getByTestId('integrity-badge')).toHaveTextContent('Not configured');
    });
    expect(screen.queryByText(/Invalid/)).not.toBeInTheDocument();
    expect(screen.getByText('No audit log file is configured')).toBeInTheDocument();
  });
});
