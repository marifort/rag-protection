import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../auth/AuthContext';
import { IdpAuthControl } from './IdpAuthControl';
import { ToastProvider } from './ToastContext';

const JWT =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwbGF0Zm9ybS5hZG1pbiJ9.signature-part-aaaaaaaaaaaaaaaa';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function stubFetch(health: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/health')) {
      return jsonResponse({ status: 'healthy', ...health });
    }
    if (url.includes('/admin/auth/me')) {
      return jsonResponse({
        roles: ['policy_admin'],
        auth_method: 'oidc',
        allowed_tenants: ['default'],
      });
    }
    if (url.includes('/v1/auth/me')) {
      return jsonResponse({
        subject: 'platform.admin',
        groups: ['engineering'],
        auth_method: 'oidc',
        email: 'platform.admin@example.com',
      });
    }
    return jsonResponse({});
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function renderControl() {
  return render(
    <ToastProvider>
      <AuthProvider defaultBaseUrl="http://localhost:8090">
        <IdpAuthControl />
      </AuthProvider>
    </ToastProvider>,
  );
}

describe('IdpAuthControl CE leftover JWT', () => {
  it('hides Sign in on CE when the user bearer is a demo token', async () => {
    const fetchMock = stubFetch({ oidc_enabled: true });
    window.localStorage.setItem('ragProtectionUiUserToken', 'employee-demo-token');
    window.localStorage.setItem('ragProtectionUiAdminToken', 'rag-admin-demo-key');
    renderControl();

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('/health'))).toBe(true);
    });
    expect(screen.queryByRole('button', { name: /Sign in with IdP/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sign out/ })).not.toBeInTheDocument();
  });

  it('shows Sign out on CE when a leftover IdP JWT is in the user bearer', async () => {
    stubFetch({ oidc_enabled: true });
    window.localStorage.setItem('ragProtectionUiUserToken', JWT);
    window.localStorage.setItem('ragProtectionUiAdminToken', JWT);
    window.localStorage.setItem('ragProtectionUiIdpEmail', 'platform.admin@example.com');
    window.localStorage.setItem('ragProtectionUiIdpEmailForToken', JWT);
    renderControl();

    expect(await screen.findByRole('button', { name: 'Sign out (platform.admin@example.com)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sign in with IdP/ })).not.toBeInTheDocument();
  });

  it('restores the demo user token on Sign out and hides the control on CE', async () => {
    stubFetch({ oidc_enabled: true });
    window.localStorage.setItem('ragProtectionUiUserToken', JWT);
    window.localStorage.setItem('ragProtectionUiAdminToken', JWT);
    renderControl();

    fireEvent.click(await screen.findByRole('button', { name: /^Sign out/ }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Sign out/ })).not.toBeInTheDocument();
    });
    expect(window.localStorage.getItem('ragProtectionUiUserToken')).toBe('employee-demo-token');
    expect(window.localStorage.getItem('ragProtectionUiAdminToken')).toBe('rag-admin-demo-key');
    expect(screen.queryByRole('button', { name: /Sign in with IdP/ })).not.toBeInTheDocument();
  });
});

describe('IdpAuthControl EE Sign in', () => {
  it('shows Sign in with IdP when UI login is available and no JWT is stored', async () => {
    stubFetch({
      oidc_enabled: true,
      oidc_ui_login_available: true,
      oidc_ui_login_configured: true,
      enterprise_installed: true,
    });
    window.localStorage.setItem('ragProtectionUiUserToken', 'employee-demo-token');
    window.localStorage.setItem('ragProtectionUiAdminToken', 'rag-admin-demo-key');
    renderControl();

    expect(await screen.findByRole('button', { name: 'Sign in with IdP' })).toBeInTheDocument();
  });
});
