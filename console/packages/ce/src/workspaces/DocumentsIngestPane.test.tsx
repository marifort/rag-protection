import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderCePane } from '../test/renderPane';
import { DocumentsIngestPane } from './DocumentsIngestPane';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockDocumentsFetch(opts?: { quarantined?: boolean }) {
  const quarantined = opts?.quarantined ?? false;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = String(url);
      const method = (init?.method || 'GET').toUpperCase();

      if (path.includes('/admin/auth/me')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify({ roles: ['ingest_admin'] }),
        });
      }
      if (path.includes('/v1/auth/me')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              subject: 'alice.engineer',
              tenant_id: 'default',
              groups: ['engineering', 'all-staff'],
            }),
        });
      }
      if (path.includes('/v1/documents/quarantined')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              count: quarantined ? 1 : 0,
              documents: quarantined
                ? [
                    {
                      document_id: 'held-1',
                      title: 'Suspicious',
                      quarantine_reason: 'injection',
                      quarantine_risk_score: 0.55,
                      quarantine_scanners: ['injection'],
                    },
                  ]
                : [],
            }),
        });
      }
      if (method === 'DELETE' && path.includes('/v1/documents/')) {
        return Promise.resolve({
          ok: true,
          text: async () => JSON.stringify({ deleted: true, document_id: 'faq-1' }),
        });
      }
      if (method === 'POST' && path.includes('/v1/ingest')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              document_id: 'doc-custom-1',
              chunks: 1,
              status: 'ok',
            }),
        });
      }
      if (path.includes('/v1/documents')) {
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              count: 1,
              documents: [
                {
                  document_id: 'faq-1',
                  title: 'Company FAQ',
                  allowed_groups: ['all-staff'],
                  chunk_count: 2,
                  created_at: 1_700_000_000,
                },
              ],
            }),
        });
      }
      return Promise.resolve({ ok: true, text: async () => '{}' });
    }),
  );
}

describe('DocumentsIngestPane', () => {
  it('prompts for tokens when missing', () => {
    renderCePane(DocumentsIngestPane, {
      adminToken: '',
      userToken: '',
      activeWorkspaceId: 'documents',
    });
    expect(screen.getByRole('heading', { name: 'Ingest Document' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Corpus Documents' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Held \(quarantined\)/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Set admin bearer token/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Set a user bearer token/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Inspect' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Preview/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /CHALLENGE Queue/i })).not.toBeInTheDocument();
  });

  it('lists corpus documents and supports ingest', async () => {
    mockDocumentsFetch();
    renderCePane(DocumentsIngestPane, {
      adminToken: 'rag-admin-demo-key',
      userToken: 'employee-demo-token',
      activeWorkspaceId: 'documents',
    });

    expect(await screen.findByText('faq-1')).toBeInTheDocument();
    expect(screen.getByText('Company FAQ')).toBeInTheDocument();
    expect(screen.getByText(/Corpus tenant "default"/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Fill sample' }));
    fireEvent.click(screen.getByLabelText('audit_debug'));
    fireEvent.click(screen.getByRole('button', { name: 'Ingest Document' }));

    await waitFor(() => {
      expect(screen.getByText(/status=/i)).toBeInTheDocument();
    });

    const ingestCall = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url, init]) =>
        String(url).includes('/v1/ingest') && String(init?.method || 'GET').toUpperCase() === 'POST',
    );
    expect(ingestCall).toBeTruthy();
    const payload = JSON.parse(String(ingestCall?.[1]?.body || '{}'));
    expect(payload.audit_debug).toBe(true);
  });

  it('lists quarantined metadata without content preview controls', async () => {
    mockDocumentsFetch({ quarantined: true });
    renderCePane(DocumentsIngestPane, {
      adminToken: 'rag-admin-demo-key',
      userToken: 'employee-demo-token',
      activeWorkspaceId: 'documents',
    });

    expect(await screen.findByText('held-1')).toBeInTheDocument();
    expect(screen.getByText('Suspicious')).toBeInTheDocument();
    expect(screen.getAllByText('injection').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Inspect' })).not.toBeInTheDocument();
  });

  it('deletes a corpus document after confirm', async () => {
    mockDocumentsFetch();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderCePane(DocumentsIngestPane, {
      adminToken: 'rag-admin-demo-key',
      userToken: 'employee-demo-token',
      activeWorkspaceId: 'documents',
    });

    expect(await screen.findByText('faq-1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });
  });
});
