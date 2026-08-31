import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider, useAuth } from './AuthContext';
import { ToastProvider } from '../layout/ToastContext';

const JWT =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwbGF0Zm9ybS5hZG1pbiJ9.signature-part-aaaaaaaaaaaaaaaa';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
});

beforeEach(() => {
  window.history.replaceState({}, '', '/');
});

function AuthProbe() {
  const { adminToken, userToken, userEmail } = useAuth();
  return (
    <div>
      <span data-testid="admin-token">{adminToken}</span>
      <span data-testid="user-token">{userToken}</span>
      <span data-testid="user-email">{userEmail}</span>
    </div>
  );
}

function renderAuth() {
  return render(
    <ToastProvider>
      <AuthProvider defaultBaseUrl="http://localhost:8090">
        <AuthProbe />
      </AuthProvider>
    </ToastProvider>,
  );
}

describe('AuthProvider OIDC login', () => {
  it('copies the IdP access token into User and Admin bearer on ticket redeem', async () => {
    window.history.replaceState({}, '', '/?oidc_login=ok&oidc_ticket=ticket-1');

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/admin/auth/oidc/login/ticket')) {
        return new Response(JSON.stringify({ access_token: JWT, email: 'platform.admin@example.com' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/admin/auth/me')) {
        return new Response(
          JSON.stringify({ roles: ['policy_admin'], auth_method: 'oidc', allowed_tenants: ['default'] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url.includes('/v1/auth/me')) {
        return new Response(
          JSON.stringify({
            subject: 'platform.admin',
            groups: ['rag-platform-admins'],
            auth_method: 'oidc',
            email: 'platform.admin@example.com',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user-token')).toHaveTextContent(JWT);
      expect(screen.getByTestId('admin-token')).toHaveTextContent(JWT);
    });
    expect(screen.getByTestId('user-email')).toHaveTextContent('platform.admin@example.com');
    expect(window.localStorage.getItem('ragProtectionUiAdminToken')).toBe(JWT);
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('/admin/auth/oidc/login/ticket'))).toBe(
      true,
    );
  });

  it('still populates Admin bearer when the IdP user has no operator roles', async () => {
    window.history.replaceState({}, '', '/?oidc_login=ok&oidc_ticket=ticket-2');

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const authorization = new Headers(init?.headers).get('Authorization') || '';
        if (url.includes('/admin/auth/oidc/login/ticket')) {
          return new Response(JSON.stringify({ access_token: JWT, email: 'bob.hr@example.com' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/admin/auth/me')) {
          if (authorization.includes(JWT)) {
            return new Response(JSON.stringify({ detail: 'Invalid admin bearer token' }), {
              status: 403,
              headers: { 'Content-Type': 'application/json' },
            });
          }
          return new Response(
            JSON.stringify({
              roles: ['policy_admin', 'ingest_admin'],
              auth_method: 'admin_token',
              allowed_tenants: ['default'],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/v1/auth/me')) {
          return new Response(
            JSON.stringify({
              subject: 'bob.hr',
              groups: ['hr', 'all-staff'],
              auth_method: 'oidc',
              email: 'bob.hr@example.com',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderAuth();

    await waitFor(() => {
      expect(screen.getByTestId('user-token')).toHaveTextContent(JWT);
      expect(screen.getByTestId('admin-token')).toHaveTextContent(JWT);
    });
    expect(screen.queryByText(/Admin bearer token rejected/i)).not.toBeInTheDocument();
  });
});
