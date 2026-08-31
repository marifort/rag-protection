import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderCePane } from '../test/renderPane';
import { QueryLabPane } from './QueryLabPane';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('QueryLabPane toast notifications', () => {
  it('shows an error toast when query is empty', async () => {
    renderCePane(QueryLabPane);
    fireEvent.change(screen.getByLabelText('Query'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run Query' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Enter a query first.');
  });

  it('shows audit_debug guidance when admin token is missing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        const path = String(url);
        if (path.includes('/v1/query')) {
          return Promise.resolve({
            ok: true,
            text: async () => JSON.stringify({ answer: 'ok', subject: 'employee-1' }),
          });
        }
        if (path.includes('/admin/auth/me')) {
          return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: [] }) });
        }
        return Promise.resolve({ ok: true, text: async () => '{}' });
      }),
    );

    renderCePane(QueryLabPane, { adminToken: '' });
    fireEvent.click(screen.getByLabelText('audit_debug'));
    fireEvent.click(screen.getByRole('button', { name: 'Run Query' }));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'audit_debug enabled — set admin token and open Audit Log to inspect previews.',
      ),
    );
  });

  it('sends include_retrieval_trace and renders the explainability table', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = String(url);
      if (path.includes('/v1/query')) {
        expect(JSON.parse(String(init?.body ?? '{}'))).toMatchObject({
          include_retrieval_trace: true,
        });
        return Promise.resolve({
          ok: true,
          text: async () =>
            JSON.stringify({
              answer: 'ok',
              subject: 'employee-1',
              retrieval_trace: [
                {
                  document_id: 'payroll-q1',
                  title: 'Payroll',
                  score: 0.8,
                  outcome: 'excluded_acl',
                  detail: 'required groups [hr]',
                },
                {
                  document_id: 'faq-1',
                  title: 'FAQ',
                  score: 0.5,
                  outcome: 'selected',
                  detail: 'top_4 by score',
                },
              ],
            }),
        });
      }
      if (path.includes('/admin/auth/me')) {
        return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: [] }) });
      }
      return Promise.resolve({ ok: true, text: async () => '{}' });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderCePane(QueryLabPane);
    fireEvent.click(screen.getByLabelText('include_retrieval_trace'));
    fireEvent.click(screen.getByRole('button', { name: 'Run Query' }));

    expect(await screen.findByRole('heading', { name: 'Why this was retrieved' })).toBeInTheDocument();
    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(screen.getByText('Used')).toBeInTheDocument();
    expect(screen.getByText('payroll-q1')).toBeInTheDocument();
  });

  it('does not render retrieval_trace rows when include_retrieval_trace is off', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = String(url);
        if (path.includes('/v1/query')) {
          expect(JSON.parse(String(init?.body ?? '{}'))).toMatchObject({
            include_retrieval_trace: false,
          });
          return Promise.resolve({
            ok: true,
            text: async () =>
              JSON.stringify({
                answer: 'ok',
                subject: 'employee-1',
                // Stale/policy payloads must not appear unless the toggle was on.
                retrieval_trace: [
                  {
                    document_id: 'should-not-render',
                    title: 'Hidden',
                    score: 0.9,
                    outcome: 'selected',
                    detail: 'trace unavailable for store backend',
                  },
                ],
              }),
          });
        }
        if (path.includes('/admin/auth/me')) {
          return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: [] }) });
        }
        return Promise.resolve({ ok: true, text: async () => '{}' });
      }),
    );

    renderCePane(QueryLabPane);
    fireEvent.click(screen.getByRole('button', { name: 'Run Query' }));

    expect(
      await screen.findByText(
        'Turn on include_retrieval_trace and run the question again to fill this table.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('should-not-render')).not.toBeInTheDocument();
    expect(screen.queryByText('Used')).not.toBeInTheDocument();
  });

  it('runs Ungrounded demo and highlights hard-gate failure + unsupported claims', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = String(url);
        if (path.includes('/v1/query')) {
          const body = JSON.parse(String(init?.body ?? '{}')) as { query?: string };
          expect(body.query).toContain('Q3 revenue');
          return Promise.resolve({
            ok: true,
            text: async () =>
              JSON.stringify({
                answer: '',
                blocked: true,
                block_reason: 'citation_hard_gate_failed',
                query_verdict: 'allow',
                output_verdict: 'block',
                subject: 'employee-1',
                citations: {
                  passed: false,
                  hard_gate_failed: true,
                  unsupported_count: 1,
                  coverage_ratio: 0.5,
                  claims: [
                    {
                      sentence: 'Support hours are Monday through Friday.',
                      chunk_id: 'faq-0',
                      supported: true,
                    },
                    {
                      sentence: 'Revenue grew forty percent last quarter.',
                      chunk_id: null,
                      supported: false,
                    },
                  ],
                },
              }),
          });
        }
        if (path.includes('/admin/auth/me')) {
          return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: [] }) });
        }
        return Promise.resolve({ ok: true, text: async () => '{}' });
      }),
    );

    renderCePane(QueryLabPane);
    fireEvent.click(screen.getByRole('button', { name: 'Ungrounded demo' }));

    expect(await screen.findByText('Blocked — citation hard gate')).toBeInTheDocument();
    expect(screen.getByText('Hard citation gate failed')).toBeInTheDocument();
    expect(screen.getByText('unsupported')).toBeInTheDocument();
    expect(screen.getByText('Revenue grew forty percent last quarter.')).toBeInTheDocument();
  });
});

describe('QueryLabPane IdP identity preset', () => {
  const oidcJwt =
    'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJnb29nbGUtb2F1dGgyfDEwIn0.signature';

  it('freezes the preset to IdP token roles when a JWT user bearer is active', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        const path = String(url);
        if (path.includes('/v1/auth/me')) {
          return Promise.resolve({
            ok: true,
            text: async () =>
              JSON.stringify({
                subject: 'google-oauth2|104',
                groups: ['all-staff', 'engineering'],
                auth_method: 'oidc',
              }),
          });
        }
        if (path.includes('/admin/auth/me')) {
          return Promise.resolve({ ok: true, text: async () => JSON.stringify({ roles: [] }) });
        }
        return Promise.resolve({ ok: true, text: async () => '{}' });
      }),
    );

    renderCePane(QueryLabPane, { userToken: oidcJwt });

    const select = await screen.findByLabelText('Identity (IdP)');
    expect(select).toBeDisabled();
    expect(select).toHaveDisplayValue('IdP token — all-staff, engineering');
    expect(screen.queryByRole('option', { name: /employee-demo-token/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Sign out \(top right\) to switch identities/)).toBeInTheDocument();
  });
});

describe('QueryLabPane DLP label samples', () => {
  const samples = [
    {
      button: 'PHI sample',
      query: 'Look up patient Jane Martinez, MRN 1234567890, SSN 123-45-6789, SIN 046-454-286.',
    },
    {
      button: 'PCI sample',
      query: 'The card on file is Visa 4111111111111111.',
    },
    {
      button: 'GDPR sample',
      query: 'Confirm payout IBAN DE89370400440532013000.',
    },
    {
      button: 'INTERNAL sample',
      query: 'What is the PTO balance for EMP-442198?',
    },
  ] as const;

  it('fills queries that contain tokens for each DLP label', () => {
    renderCePane(QueryLabPane);
    const box = screen.getByLabelText('Query');
    for (const sample of samples) {
      fireEvent.click(screen.getByRole('button', { name: sample.button }));
      expect(box).toHaveValue(sample.query);
    }
  });
});
