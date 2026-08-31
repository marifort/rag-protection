import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderCePane } from '../test/renderPane';
import { OverviewPane } from './OverviewPane';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockOverviewFetch(opts?: { withPair?: boolean }) {
  const withPair = opts?.withPair ?? true;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      if (path.includes('/admin/auth/me')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify({ roles: ['audit_reader'] }),
        });
      }
      if (path.includes('/health')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify({ status: 'ok' }),
        });
      }
      if (path.includes('/metrics')) {
        return Promise.resolve({
          ok: true,
          text: async () => 'rag_queries_total{decision="allowed"} 1\n',
        });
      }
      if (path.includes('/admin/overview/stats')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              challenges_pending: 2,
              ingest_quarantined: 1,
              challenge_approved: 0,
              challenge_rejected: 0,
            }),
        });
      }
      if (path.includes('kind=extraction_suspected')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              events: withPair
                ? [
                    {
                      kind: 'extraction_suspected',
                      subject: 'alice.engineer',
                      tenant_id: 'default',
                      timestamp: 1_752_048_000,
                    },
                  ]
                : [],
              total: withPair ? 1 : 0,
            }),
        });
      }
      if (path.includes('kind=canary_triggered')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              events: withPair
                ? [
                    {
                      kind: 'canary_triggered',
                      subject: 'alice.engineer',
                      tenant_id: 'default',
                      timestamp: 1_752_048_100,
                    },
                  ]
                : [],
              total: withPair ? 1 : 0,
            }),
        });
      }
      return Promise.resolve({ ok: true, text: async () => '{}' });
    }),
  );
}

describe('OverviewPane exfil strip', () => {
  it('shows high-confidence pair and navigates to Audit', async () => {
    mockOverviewFetch({ withPair: true });
    const onWorkspaceChange = vi.fn();
    renderCePane(OverviewPane, {
      adminToken: 'admin-token',
      activeWorkspaceId: 'overview',
      onWorkspaceChange,
    });

    expect(await screen.findByRole('heading', { name: 'Suspected data theft' })).toBeInTheDocument();
    expect(await screen.findByText('alice.engineer')).toBeInTheDocument();
    expect((await screen.findAllByText('Awaiting review')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('1 high-confidence')).toBeInTheDocument();
    expect(screen.getAllByText('same hour').length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole('button', { name: 'Open in Audit' }));
    await waitFor(() => expect(onWorkspaceChange).toHaveBeenCalledWith('audit'));
  });

  it('shows empty pair state when kinds do not overlap', async () => {
    mockOverviewFetch({ withPair: false });
    renderCePane(OverviewPane, { adminToken: 'admin-token', activeWorkspaceId: 'overview' });
    expect(await screen.findByText('0 pairs')).toBeInTheDocument();
  });
});
