import { useCallback, useEffect, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import { looksLikeJwt } from '../auth/tokens';
import { useToast } from './ToastContext';

/** Dispatched after Reload Policy so the hero Sign-in control re-checks /health. */
export const OIDC_UI_STATUS_EVENT = 'rag-oidc-ui-status';

export function notifyOidcUiStatusChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(OIDC_UI_STATUS_EVENT));
}

export type IdpAuthControlProps = {
  /** Re-check OIDC UI login availability (e.g. shell refresh tick). */
  refreshTick?: number;
};

/**
 * Header Sign in / Sign out control.
 * Sign in with IdP is EE-only (`oidc_ui_login_available`).
 * Sign out is shown whenever the user bearer is an IdP JWT (CE paste, leftover
 * EE session on the same origin, or EE Sign-in).
 */
export function IdpAuthControl({ refreshTick = 0 }: IdpAuthControlProps) {
  const { api, baseUrl, userToken, userEmail, signOutIdp } = useAuth();
  const { toast } = useToast();
  const [oidcUiLoginAvailable, setOidcUiLoginAvailable] = useState(false);

  const idpUserTokenActive = looksLikeJwt(userToken);

  const refreshOidcUiLoginFlag = useCallback(async () => {
    try {
      const health = await api.health();
      setOidcUiLoginAvailable(health.oidc_ui_login_available === true);
    } catch {
      setOidcUiLoginAvailable(false);
    }
  }, [api]);

  useEffect(() => {
    void refreshOidcUiLoginFlag();
  }, [refreshOidcUiLoginFlag, baseUrl, refreshTick]);

  useEffect(() => {
    function onStatus() {
      void refreshOidcUiLoginFlag();
    }
    window.addEventListener(OIDC_UI_STATUS_EVENT, onStatus);
    return () => window.removeEventListener(OIDC_UI_STATUS_EVENT, onStatus);
  }, [refreshOidcUiLoginFlag]);

  function normalizeOrigin(url: string): string {
    try {
      return new URL(url).origin;
    } catch {
      return url.replace(/\/+$/, '');
    }
  }

  function signInWithIdp() {
    const root = window.location.origin;
    if (baseUrl && normalizeOrigin(baseUrl) !== normalizeOrigin(root)) {
      toast(
        `Proxy base URL (${baseUrl}) differs from this page (${root}). IdP sign-in uses ${root}; set Proxy base URL to match.`,
        'err',
      );
    }
    window.location.assign(`${root}/admin/auth/oidc/login/start`);
  }

  if (idpUserTokenActive) {
    const label = userEmail ? `Sign out (${userEmail})` : 'Sign out';
    return (
      <button
        type="button"
        className="idp-auth-btn signed-in"
        onClick={() => signOutIdp()}
        title={
          userEmail
            ? `Sign out ${userEmail} — clear IdP access token and restore demo user / prior admin key`
            : 'Clear IdP access token and restore demo user / prior admin key'
        }
      >
        {label}
      </button>
    );
  }

  if (!oidcUiLoginAvailable) return null;

  return (
    <button
      type="button"
      className="idp-auth-btn"
      onClick={() => signInWithIdp()}
      title="OAuth authorization code + PKCE via IdP"
    >
      Sign in with IdP
    </button>
  );
}
