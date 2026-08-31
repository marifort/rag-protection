import { useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ADMIN_BEFORE_IDP_KEY, isReplaceableAdminToken, looksLikeJwt } from '../auth/tokens';
import { BearerTokenField } from './BearerTokenField';
import { notifyOidcUiStatusChanged } from './IdpAuthControl';
import { useOperationResult } from './OperationResultContext';
import { useToast } from './ToastContext';

export type OperatorToolbarProps = {
  onRefresh?: () => void | Promise<void>;
  onTenantChange?: () => void;
};

const DEMO_ADMIN_KEY = 'rag-admin-demo-key';

export function OperatorToolbar({ onRefresh, onTenantChange }: OperatorToolbarProps) {
  const {
    adminToken,
    userToken,
    baseUrl,
    operatorTenant,
    adminRoles,
    adminAuthMethod,
    allowedTenants,
    setAdminToken,
    setUserToken,
    setBaseUrl,
    setOperatorTenant,
    api,
    adminFetchInit,
    userSubject,
    userEmail,
    userGroups,
    userAuthMethod,
    adminUsesIdpToken,
    idpAdminMapped,
    applyIdpTokenAsAdmin,
  } = useAuth();
  const { setLastOperation } = useOperationResult();
  const { toast } = useToast();
  const [oidcUiLoginAvailable, setOidcUiLoginAvailable] = useState(false);
  const [oidcUiLoginConfigured, setOidcUiLoginConfigured] = useState(false);
  const [oidcEnabled, setOidcEnabled] = useState(false);

  const idpUserTokenActive = looksLikeJwt(userToken);
  const idpSession = adminUsesIdpToken;
  const showUseIdpAsAdmin =
    idpUserTokenActive && !adminUsesIdpToken && (idpAdminMapped || isReplaceableAdminToken(adminToken));

  function setIdpSessionToken(value: string) {
    setUserToken(value);
    if (looksLikeJwt(value)) {
      setAdminToken(value);
      return;
    }
    const prior = sessionStorage.getItem(ADMIN_BEFORE_IDP_KEY) || DEMO_ADMIN_KEY;
    sessionStorage.removeItem(ADMIN_BEFORE_IDP_KEY);
    setAdminToken(prior);
  }

  async function refreshOidcUiLoginFlag(): Promise<{
    available: boolean;
    configured: boolean;
    enabled: boolean;
  }> {
    try {
      const health = await api.health();
      const available = health.oidc_ui_login_available === true;
      const configured = health.oidc_ui_login_configured === true;
      const enabled = health.oidc_enabled === true;
      setOidcUiLoginAvailable(available);
      setOidcUiLoginConfigured(configured);
      setOidcEnabled(enabled);
      notifyOidcUiStatusChanged();
      return { available, configured, enabled };
    } catch {
      setOidcUiLoginAvailable(false);
      setOidcUiLoginConfigured(false);
      setOidcEnabled(false);
      notifyOidcUiStatusChanged();
      return { available: false, configured: false, enabled: false };
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const health = await api.health();
        if (cancelled) return;
        const enabled = health.oidc_enabled === true;
        setOidcUiLoginAvailable(health.oidc_ui_login_available === true);
        setOidcUiLoginConfigured(health.oidc_ui_login_configured === true);
        setOidcEnabled(enabled);
        // IdP JWT cannot authorize admin APIs while OIDC is off — restore demo admin for reload.
        if (!enabled && looksLikeJwt(adminToken)) {
          setAdminToken(DEMO_ADMIN_KEY);
          toast(
            'OIDC is disabled in the running proxy — restored Admin bearer to rag-admin-demo-key so Reload Policy can re-enable it.',
            'ok',
          );
        }
      } catch {
        if (!cancelled) {
          setOidcUiLoginAvailable(false);
          setOidcUiLoginConfigured(false);
          setOidcEnabled(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // Intentionally omit adminToken: only react to api/baseUrl changes / mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot restore when health says OIDC off
  }, [api, baseUrl, setAdminToken, toast]);

  async function reloadPolicy() {
    try {
      const body = await api.fetchJson('/admin/reload-policy', {
        method: 'POST',
        ...adminFetchInit(),
      });
      setLastOperation(body);
      const flags = await refreshOidcUiLoginFlag();
      if (flags.available) {
        toast('Policy reloaded — Sign in with IdP is available.', 'ok');
      } else if (flags.configured && !flags.enabled) {
        toast(
          'Policy reloaded, but oidc.enabled is still false in the running proxy. Confirm acl_policy.yaml and try again.',
          'err',
        );
      } else if (flags.configured && flags.enabled && !flags.available) {
        toast(
          'OIDC is on but UI login is incomplete — set ui_client_id and ui_redirect_uri, then reload again.',
          'err',
        );
      } else {
        toast('Policy reloaded.', 'ok');
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setLastOperation({ status: 'error', detail: message });
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 401 || status === 403) {
        const hint = looksLikeJwt(adminToken)
          ? ' Admin bearer looks like an IdP JWT — while OIDC is off in memory, set Admin bearer to rag-admin-demo-key, then Reload Policy again.'
          : ' Check Admin bearer has policy_admin (rag-admin-demo-key).';
        toast(`Reload Policy failed: ${message}.${hint}`, 'err');
        // Offer recovery path immediately.
        if (looksLikeJwt(adminToken)) {
          setAdminToken(DEMO_ADMIN_KEY);
        }
      } else {
        toast(`Reload Policy failed: ${message}`, 'err');
      }
      await refreshOidcUiLoginFlag();
    }
  }

  const toolbarActions = (
    <div className={`toolbar-actions${idpSession ? ' toolbar-actions-compact' : ''}`}>
      {showUseIdpAsAdmin ? (
        <button
          type="button"
          onClick={() => void applyIdpTokenAsAdmin()}
          title="Copy IdP JWT into Admin bearer when oidc.admin_role_map matches (demo credibility)"
        >
          Use IdP as admin
        </button>
      ) : null}
      {!oidcUiLoginAvailable && oidcUiLoginConfigured && !oidcEnabled ? (
        <span
          className="badge"
          title="ui_client_* is set but oidc.enabled is false in the running proxy"
        >
          IdP Sign-in: set oidc.enabled true → Admin = rag-admin-demo-key → Reload Policy
        </span>
      ) : null}
      {onRefresh ? (
        <button type="button" onClick={() => void onRefresh()}>
          Refresh
        </button>
      ) : null}
      <button type="button" className="warn" onClick={() => void reloadPolicy()}>
        Reload Policy
      </button>
    </div>
  );

  const tenantField = (
    <label>
      Operator tenant
      <select
        value={operatorTenant}
        onChange={(event) => {
          setOperatorTenant(event.target.value);
          onTenantChange?.();
        }}
      >
        {allowedTenants.map((tenant) => (
          <option key={tenant} value={tenant}>
            {tenant}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <section className="toolbar-panel" aria-labelledby="operator-session-heading">
      <h3 id="operator-session-heading">Session</h3>
      <div className={`toolbar${idpSession ? ' toolbar-idp-session' : ''}`}>
      <label>
        Proxy base URL
        <input
          value={baseUrl}
          onChange={(event) => setBaseUrl(event.target.value)}
          placeholder="http://localhost:8090"
        />
        <span style={{ display: 'block', fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
          Server root only (e.g. <code>http://localhost:8090</code>) — not <code>/ui</code>.
          Must match this page&apos;s host/port for IdP sign-in.
        </span>
      </label>
      {idpSession ? (
        <BearerTokenField
          label="IdP access token"
          value={userToken}
          onChange={setIdpSessionToken}
          title="Same access token for User (ACL) and Admin (operator) APIs"
        />
      ) : (
        <BearerTokenField
          label="Admin bearer token"
          value={adminToken}
          onChange={setAdminToken}
          placeholder="RAG_ADMIN_API_KEY"
          title="Demo key, break-glass RAG_ADMIN_API_KEY, or IdP JWT with admin_role_map"
        />
      )}
      {idpSession ? (
        <label
          className="role-panel"
          title="One IdP access token: ACL groups from GET /v1/auth/me, operator roles from GET /admin/auth/me"
        >
          IdP session
          <div className="badge role-panel-body">
            <span className="role-badge-group">
              {userEmail ? (
                <span className="pill" title="email">
                  {userEmail}
                </span>
              ) : null}
              {userSubject && userSubject !== userEmail ? (
                <span className="pill" title="subject">
                  {userSubject}
                </span>
              ) : null}
              {userAuthMethod || adminAuthMethod ? (
                <span className="pill" title="auth_method">
                  {userAuthMethod || adminAuthMethod}
                </span>
              ) : null}
              <span className="role-cluster-label">ACL</span>
              {userGroups.length ? (
                userGroups.map((group) => (
                  <span key={`acl-${group}`} className="pill" title="ACL group">
                    {group}
                  </span>
                ))
              ) : (
                <span className="pill">groups: —</span>
              )}
              <span className="role-cluster-label">Admin</span>
              {adminRoles.length ? (
                adminRoles.map((role) => (
                  <span key={`admin-${role}`} className="pill" title="operator role">
                    {role}
                  </span>
                ))
              ) : (
                <span className="pill">no operator roles</span>
              )}
            </span>
          </div>
        </label>
      ) : (
        <label className="role-panel" title="Operator roles from GET /admin/auth/me">
          Admin roles
          <div className="badge role-panel-body">
            <span className="role-badge-group">
              {adminRoles.length || adminAuthMethod ? (
                <>
                  {adminAuthMethod ? (
                    <span className="pill" title="auth_method">
                      {adminAuthMethod}
                    </span>
                  ) : null}
                  {adminRoles.length ? (
                    adminRoles.map((role) => (
                      <span key={role} className="pill">
                        {role}
                      </span>
                    ))
                  ) : (
                    <span className="pill">roles: —</span>
                  )}
                </>
              ) : (
                <span className="pill">roles: —</span>
              )}
            </span>
          </div>
        </label>
      )}
      {idpSession ? (
        <div className="toolbar-idp-aside">
          {tenantField}
          {toolbarActions}
        </div>
      ) : (
        tenantField
      )}
      {idpSession ? null : (
        <BearerTokenField
          label="User bearer token"
          value={userToken}
          onChange={setUserToken}
          placeholder="employee-demo-token"
          title="Demo person token, or IdP access JWT from Sign in with IdP / paste"
        />
      )}
      {idpSession ? null : (
        <div className="toolbar-user-row">
          <label
            className="role-panel toolbar-user-roles"
            title="Resolved from GET /v1/auth/me for the current user bearer (IdP email / roles used for ACL)"
          >
            User roles
            <div className="badge role-panel-body">
              <span className="role-badge-group">
                {userEmail || userSubject || userGroups.length || userAuthMethod ? (
                  <>
                    {userEmail ? (
                      <span className="pill" title="email">
                        {userEmail}
                      </span>
                    ) : null}
                    {userSubject && userSubject !== userEmail ? (
                      <span className="pill" title="subject">
                        {userSubject}
                      </span>
                    ) : null}
                    {userAuthMethod ? (
                      <span className="pill" title="auth_method">
                        {userAuthMethod}
                      </span>
                    ) : null}
                    {userGroups.length ? (
                      userGroups.map((group) => (
                        <span key={group} className="pill" title="group / role">
                          {group}
                        </span>
                      ))
                    ) : (
                      <span className="pill">roles: —</span>
                    )}
                  </>
                ) : (
                  <span className="pill">roles: —</span>
                )}
              </span>
            </div>
          </label>
          {toolbarActions}
        </div>
      )}
      </div>
    </section>
  );
}
