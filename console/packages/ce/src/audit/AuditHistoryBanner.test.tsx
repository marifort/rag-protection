import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider, ToastProvider } from '@rag-protection/console-core';

import { RefreshProvider } from '../refresh/RefreshContext';
import { AuditHistoryBanner } from './AuditHistoryBanner';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockFetch(responses: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      if (path.includes('/health')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify(responses.health),
        });
      }
      if (path.includes('/admin/auth/me')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify(responses.adminMe ?? { roles: [] }),
        });
      }
      return Promise.resolve({ ok: true, text: async () => '{}' });
    }),
  );
}

describe('AuditHistoryBanner', () => {
  it('shows the limited history warning when audit.file_sink is missing', async () => {
    mockFetch({
      health: {
        status: 'healthy',
        audit: { file_sink: null, buffer_count: 12, buffer_max: 100 },
      },
    });

    render(
      <ToastProvider>
        <AuthProvider defaultBaseUrl="http://localhost:8090">
          <RefreshProvider>
            <AuditHistoryBanner />
          </RefreshProvider>
        </AuthProvider>
      </ToastProvider>,
    );

    expect(await screen.findByText(/Limited history/)).toBeInTheDocument();
    expect(screen.getByText(/12 of 100 events/)).toBeInTheDocument();
  });

  it('renders nothing when a durable audit file sink is configured', async () => {
    mockFetch({
      health: {
        status: 'healthy',
        audit: { file_sink: '/data/audit.jsonl', buffer_count: 12, buffer_max: 100 },
      },
    });

    render(
      <ToastProvider>
        <AuthProvider defaultBaseUrl="http://localhost:8090">
          <RefreshProvider>
            <AuditHistoryBanner />
          </RefreshProvider>
        </AuthProvider>
      </ToastProvider>,
    );

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByText(/Limited history/)).not.toBeInTheDocument();
  });
});
