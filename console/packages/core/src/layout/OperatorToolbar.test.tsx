import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../auth/AuthContext';
import { OperationResultProvider } from './OperationResultContext';
import { OperatorToolbar } from './OperatorToolbar';
import { ToastProvider } from './ToastContext';

const JWT =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwbGF0Zm9ybS5hZG1pbiJ9.signature-part-aaaaaaaaaaaaaaaa';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function stubFetch(options: { adminRoles: string[]; userGroups: string[]; adminOk: boolean }) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/health')) {
        return jsonResponse({
          status: 'healthy',
          oidc_enabled: true,
          oidc_ui_login_available: true,
          oidc_ui_login_configured: true,
        });
      }
      if (url.includes('/admin/auth/me')) {
        if (!options.adminOk) {
          return jsonResponse({ detail: 'Invalid admin bearer token' }, 403);
        }
        return jsonResponse({
          roles: options.adminRoles,
          auth_method: 'oidc',
          allowed_tenants: ['default'],
        });
      }
      if (url.includes('/v1/auth/me')) {
        return jsonResponse({
          subject: 'platform.admin',
          groups: options.userGroups,
          auth_method: 'oidc',
          email: 'platform.admin@example.com',
        });
      }
      return jsonResponse({});
    }),
  );
}

function renderToolbar() {
  return render(
    <ToastProvider>
      <AuthProvider defaultBaseUrl="http://localhost:8090">
        <OperationResultProvider>
          <OperatorToolbar />
        </OperationResultProvider>
      </AuthProvider>
    </ToastProvider>,
  );
}

describe('OperatorToolbar IdP session', () => {
  it('keeps split Admin and User bearer fields for demo tokens', () => {
    stubFetch({ adminRoles: ['policy_admin'], userGroups: ['engineering'], adminOk: true });
    window.localStorage.setItem('ragProtectionUiAdminToken', 'rag-admin-demo-key');
    window.localStorage.setItem('ragProtectionUiUserToken', 'employee-demo-token');
    renderToolbar();

    expect(screen.getByRole('heading', { name: 'Session' })).toBeInTheDocument();
    expect(screen.getByLabelText('Admin bearer token')).toBeInTheDocument();
    expect(screen.getByLabelText('User bearer token')).toBeInTheDocument();
    expect(screen.queryByLabelText('IdP access token')).not.toBeInTheDocument();
    expect(screen.queryByText('IdP session')).not.toBeInTheDocument();
  });

  it('collapses to one IdP session when User and Admin share the same JWT', async () => {
    stubFetch({ adminRoles: ['policy_admin'], userGroups: ['rag-platform-admins'], adminOk: true });
    window.localStorage.setItem('ragProtectionUiAdminToken', JWT);
    window.localStorage.setItem('ragProtectionUiUserToken', JWT);
    renderToolbar();

    expect(screen.getByLabelText('IdP access token')).toBeInTheDocument();
    expect(screen.queryByLabelText('Admin bearer token')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('User bearer token')).not.toBeInTheDocument();
    expect(screen.getByText('IdP session')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload Policy' })).toBeInTheDocument();
    expect(await screen.findByText('policy_admin')).toBeInTheDocument();
    expect(screen.getByText('rag-platform-admins')).toBeInTheDocument();
    expect(screen.queryByText('Use IdP as admin')).not.toBeInTheDocument();
  });

  it('shows no operator roles in the collapsed session when the JWT is not mapped', async () => {
    stubFetch({ adminRoles: [], userGroups: ['hr', 'all-staff'], adminOk: false });
    window.localStorage.setItem('ragProtectionUiAdminToken', JWT);
    window.localStorage.setItem('ragProtectionUiUserToken', JWT);
    renderToolbar();

    expect(screen.getByLabelText('IdP access token')).toBeInTheDocument();
    expect(await screen.findByText('no operator roles')).toBeInTheDocument();
    expect(await screen.findByText('hr')).toBeInTheDocument();
  });
});
