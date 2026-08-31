import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { createApiClient, ApiError, type ApiClient } from '../api/client';
import {
  ADMIN_BEFORE_IDP_KEY,
  adminHeaders,
  clearPersistedIdpEmail,
  isReplaceableAdminToken,
  loadPersistedIdpEmail,
  loadTokens,
  looksLikeJwt,
  persistIdpEmail,
  saveTokens,
  userHeaders,
} from './tokens';
import { useToast } from '../layout/ToastContext';

const ADMIN_ROLE_ORDER = ['policy_admin', 'audit_reader', 'audit_debug_reader', 'ingest_admin'] as const;

type AdminMeResponse = {
  roles?: string[];
  allowed_tenants?: string[];
  tenants?: string[];
  auth_method?: string;
};

type UserMeResponse = {
  subject?: string;
  tenant_id?: string;
  groups?: string[];
  auth_method?: string;
  email?: string | null;
};

export type AuthState = {
  adminToken: string;
  userToken: string;
  baseUrl: string;
  operatorTenant: string;
  adminRoles: string[];
  allowedTenants: string[];
  adminAuthMethod: string;
  /** True when Admin bearer holds the same JWT as User bearer */
  adminUsesIdpToken: boolean;
  /** User JWT is accepted by GET /admin/auth/me (admin_role_map hit) */
  idpAdminMapped: boolean;
  /** Resolved from GET /v1/auth/me for the current user bearer */
  userSubject: string;
  userEmail: string;
  userGroups: string[];
  userAuthMethod: string;
  api: ApiClient;
  setAdminToken: (value: string) => void;
  setUserToken: (value: string) => void;
  setBaseUrl: (value: string) => void;
  setOperatorTenant: (value: string) => void;
  /** Copy IdP user JWT into Admin bearer (demo credibility). */
  applyIdpTokenAsAdmin: () => Promise<boolean>;
  /** Clear IdP user JWT and restore prior demo admin key when applicable. */
  signOutIdp: () => void;
  adminFetchInit: () => RequestInit;
  userFetchInit: () => RequestInit;
  tenantQuery: (url: string) => string;
};

const AuthContext = createContext<AuthState | null>(null);

export type AuthProviderProps = {
  children: ReactNode;
  defaultBaseUrl?: string;
};

function apiOrigin(baseUrl: string): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return baseUrl;
}

export function AuthProvider({ children, defaultBaseUrl = '' }: AuthProviderProps) {
  const { toast } = useToast();
  const initial = loadTokens(defaultBaseUrl);
  const [adminToken, setAdminTokenState] = useState(initial.adminToken);
  const [userToken, setUserTokenState] = useState(initial.userToken);
  const [baseUrl, setBaseUrlState] = useState(initial.baseUrl || defaultBaseUrl);
  const [operatorTenant, setOperatorTenantState] = useState(initial.operatorTenant);
  const [adminRoles, setAdminRoles] = useState<string[]>([]);
  const [allowedTenants, setAllowedTenants] = useState<string[]>(['default']);
  const [adminAuthMethod, setAdminAuthMethod] = useState('');
  const [userSubject, setUserSubject] = useState('');
  // Persist ticket/id_token email across rebuild+reload — access JWTs often omit email.
  const [userEmail, setUserEmail] = useState(() => loadPersistedIdpEmail(initial.userToken));
  const [userGroups, setUserGroups] = useState<string[]>([]);
  const [userAuthMethod, setUserAuthMethod] = useState('');
  const [idpAdminMapped, setIdpAdminMapped] = useState(false);
  const autoAdminSyncRef = useRef<string>('');
  const adminTokenRef = useRef(adminToken);
  const userTokenRef = useRef(userToken);
  adminTokenRef.current = adminToken;
  userTokenRef.current = userToken;

  const setAdminToken = useCallback((value: string) => {
    setAdminTokenState(value);
    saveTokens({ adminToken: value });
  }, []);

  const setUserToken = useCallback((value: string) => {
    setUserTokenState(value);
    saveTokens({ userToken: value });
    const persisted = loadPersistedIdpEmail(value);
    if (persisted) {
      setUserEmail(persisted);
      return;
    }
    if (!looksLikeJwt(value)) {
      clearPersistedIdpEmail();
    }
    setUserEmail('');
  }, []);

  const setBaseUrl = useCallback((value: string) => {
    setBaseUrlState(value);
    saveTokens({ baseUrl: value });
  }, []);

  const setOperatorTenant = useCallback((value: string) => {
    setOperatorTenantState(value);
    saveTokens({ operatorTenant: value });
  }, []);

  const promoteIdpToAdmin = useCallback(
    (jwt: string, currentAdmin: string, announce: boolean) => {
      if (!looksLikeJwt(jwt)) return false;
      if (currentAdmin.trim() === jwt.trim()) {
        autoAdminSyncRef.current = jwt;
        return true;
      }
      const prior = currentAdmin.trim();
      if (isReplaceableAdminToken(prior) || (prior && !looksLikeJwt(prior))) {
        sessionStorage.setItem(ADMIN_BEFORE_IDP_KEY, prior || 'rag-admin-demo-key');
      }
      setAdminTokenState(jwt);
      saveTokens({ adminToken: jwt });
      autoAdminSyncRef.current = jwt;
      adminTokenRef.current = jwt;
      if (announce) {
        toast('Admin bearer set to IdP token.', 'ok');
      }
      return true;
    },
    [toast],
  );

  const applyAccessTokenFromIdp = useCallback(
    (token: string, email: string) => {
      setUserTokenState(token);
      saveTokens({ userToken: token });
      userTokenRef.current = token;
      if (email) {
        persistIdpEmail(token, email);
        setUserEmail(email);
      }
      promoteIdpToAdmin(token, adminTokenRef.current, false);
    },
    [promoteIdpToAdmin],
  );

  const applyIdpTokenAsAdmin = useCallback(async (): Promise<boolean> => {
    const jwt = userToken.trim();
    if (!looksLikeJwt(jwt)) {
      toast('Sign in with IdP (or paste a JWT) before using it as admin.', 'err');
      return false;
    }
    try {
      const api = createApiClient(apiOrigin(baseUrl) || baseUrl);
      const body = await api.fetchJson<AdminMeResponse>('/admin/auth/me', {
        headers: adminHeaders(jwt),
      });
      const roles = Array.isArray(body.roles) ? body.roles : [];
      const method = String(body.auth_method || '').trim();
      if (!roles.length || (method !== 'oidc' && method !== 'jwt')) {
        toast(
          'IdP token has no operator admin roles via admin_role_map. Assign Auth0 roles mapped in oidc.admin_role_map, then re-sign-in.',
          'err',
        );
        setIdpAdminMapped(false);
        return false;
      }
      setIdpAdminMapped(true);
      promoteIdpToAdmin(jwt, adminToken, true);
      return true;
    } catch (err) {
      setIdpAdminMapped(false);
      const message = err instanceof ApiError ? err.message : String(err);
      toast(
        `IdP token rejected as admin (${message}). Configure oidc.admin_role_map — see OIDC_VALIDATION §3b.9.`,
        'err',
      );
      return false;
    }
  }, [adminToken, baseUrl, promoteIdpToAdmin, toast, userToken]);

  const signOutIdp = useCallback(() => {
    const priorAdmin = sessionStorage.getItem(ADMIN_BEFORE_IDP_KEY);
    sessionStorage.removeItem(ADMIN_BEFORE_IDP_KEY);
    autoAdminSyncRef.current = '';
    setUserTokenState('employee-demo-token');
    saveTokens({ userToken: 'employee-demo-token' });
    if (looksLikeJwt(adminToken) && (adminToken === userToken || priorAdmin)) {
      const restored = priorAdmin || 'rag-admin-demo-key';
      setAdminTokenState(restored);
      saveTokens({ adminToken: restored });
    }
    setIdpAdminMapped(false);
    clearPersistedIdpEmail();
    setUserEmail('');
    toast('Signed out of IdP — restored demo user token (and prior admin key if applicable).', 'ok');
  }, [adminToken, toast, userToken]);

  // EE OIDC UI login: redeem one-time ticket from /admin/auth/oidc/login/callback redirect.
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const loginStatus = params.get('oidc_login');
    const ticket = params.get('oidc_ticket');
    const loginError = params.get('oidc_login_error');

    const clearOidcParams = () => {
      const nextParams = new URLSearchParams(window.location.search);
      nextParams.delete('oidc_login');
      nextParams.delete('oidc_ticket');
      nextParams.delete('oidc_login_error');
      const next = `${window.location.pathname}${nextParams.toString() ? `?${nextParams}` : ''}${window.location.hash}`;
      window.history.replaceState({}, '', next);
    };

    if (loginStatus === 'error') {
      toast(
        `IdP sign-in failed${loginError ? `: ${loginError}` : ''}. Use paste/curl or retry Sign in with IdP.`,
        'err',
      );
      clearOidcParams();
      return;
    }

    if (loginStatus !== 'ok' || !ticket) return;

    const doneKey = `ragProtectionOidcTicket:${ticket}`;
    const cached = sessionStorage.getItem(doneKey);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as { token?: string; email?: string };
        if (parsed.token) {
          applyAccessTokenFromIdp(parsed.token, parsed.email ? String(parsed.email).trim() : '');
        } else {
          // Legacy cache: raw token string
          applyAccessTokenFromIdp(cached, '');
        }
      } catch {
        applyAccessTokenFromIdp(cached, '');
      }
      clearOidcParams();
      return;
    }

    const claimKey = 'ragProtectionOidcTicketClaim';
    if (sessionStorage.getItem(claimKey) === ticket) {
      clearOidcParams();
      return;
    }
    sessionStorage.setItem(claimKey, ticket);
    clearOidcParams();

    void (async () => {
      try {
        const api = createApiClient(window.location.origin);
        const body = await api.fetchJson<{ access_token?: string; email?: string }>(
          `/admin/auth/oidc/login/ticket?ticket=${encodeURIComponent(ticket)}`,
        );
        const token = (body.access_token || '').trim();
        if (!token) {
          sessionStorage.removeItem(claimKey);
          toast('IdP sign-in ticket returned no access token.', 'err');
          return;
        }
        const email = String(body.email || '').trim();
        sessionStorage.setItem(doneKey, JSON.stringify({ token, email }));
        sessionStorage.removeItem(claimKey);
        applyAccessTokenFromIdp(token, email);
        toast(
          email
            ? `Signed in with IdP as ${email}. Admin bearer uses the same access token.`
            : 'Signed in with IdP — user and admin bearer tokens updated.',
          'ok',
        );
      } catch (err) {
        sessionStorage.removeItem(claimKey);
        const message = err instanceof ApiError ? err.message : String(err);
        toast(`IdP sign-in ticket failed: ${message}`, 'err');
      }
    })();
  }, [applyAccessTokenFromIdp, baseUrl, toast]);

  useEffect(() => {
    let cancelled = false;

    async function validateAdminToken() {
      if (!adminToken.trim()) {
        setAdminRoles([]);
        setAdminAuthMethod('');
        return;
      }
      try {
        const api = createApiClient(apiOrigin(baseUrl) || baseUrl);
        const body = await api.fetchJson<AdminMeResponse>('/admin/auth/me', {
          headers: adminHeaders(adminToken),
        });
        if (cancelled) return;
        const roles = new Set(Array.isArray(body.roles) ? body.roles : []);
        setAdminRoles(ADMIN_ROLE_ORDER.filter((role) => roles.has(role)));
        setAdminAuthMethod(String(body.auth_method || '').trim());
        const tenants =
          Array.isArray(body.allowed_tenants) && body.allowed_tenants.length
            ? body.allowed_tenants
            : Array.isArray(body.tenants) && body.tenants.length
              ? body.tenants
              : ['default'];
        setAllowedTenants(tenants);
        setOperatorTenantState((current) => {
          if (tenants.includes(current)) return current;
          const next = tenants[0];
          saveTokens({ operatorTenant: next });
          return next;
        });
      } catch (err) {
        if (!cancelled) {
          setAdminRoles([]);
          setAdminAuthMethod('');
        }
        if (!cancelled && err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          const sameIdpJwt =
            looksLikeJwt(adminToken) && adminToken.trim() === userTokenRef.current.trim();
          if (!sameIdpJwt) {
            toast('Admin bearer token rejected. Check RAG_ADMIN_API_KEY or IdP admin roles.', 'err');
          }
        }
      }
    }

    void validateAdminToken();
    return () => {
      cancelled = true;
    };
  }, [adminToken, baseUrl, toast]);

  useEffect(() => {
    let cancelled = false;

    async function validateUserToken() {
      if (!userToken.trim()) {
        setUserSubject('');
        clearPersistedIdpEmail();
        setUserEmail('');
        setUserGroups([]);
        setUserAuthMethod('');
        return;
      }
      try {
        const api = createApiClient(apiOrigin(baseUrl) || baseUrl);
        const body = await api.fetchJson<UserMeResponse>('/v1/auth/me', {
          headers: userHeaders(userToken),
        });
        if (cancelled) return;
        setUserSubject(String(body.subject || '').trim());
        const nextEmail = String(body.email || '').trim();
        // Access tokens often omit email; keep Sign-in ticket email for JWTs when /me has none.
        setUserEmail((prev) => {
          const resolved = nextEmail || (looksLikeJwt(userToken) ? prev || loadPersistedIdpEmail(userToken) : '');
          if (resolved && looksLikeJwt(userToken)) {
            persistIdpEmail(userToken, resolved);
          } else if (!looksLikeJwt(userToken)) {
            clearPersistedIdpEmail();
          }
          return resolved;
        });
        setUserGroups(Array.isArray(body.groups) ? body.groups.map(String) : []);
        setUserAuthMethod(String(body.auth_method || '').trim());
      } catch {
        if (!cancelled) {
          setUserSubject('');
          if (!looksLikeJwt(userToken)) {
            clearPersistedIdpEmail();
            setUserEmail('');
          }
          setUserGroups([]);
          setUserAuthMethod('');
        }
      }
    }

    void validateUserToken();
    return () => {
      cancelled = true;
    };
  }, [userToken, baseUrl]);

  // Demo credibility: when user JWT maps via admin_role_map, replace static demo admin key.
  useEffect(() => {
    let cancelled = false;
    const jwt = userToken.trim();
    if (!looksLikeJwt(jwt)) {
      setIdpAdminMapped(false);
      autoAdminSyncRef.current = '';
      return;
    }

    void (async () => {
      try {
        const api = createApiClient(apiOrigin(baseUrl) || baseUrl);
        const body = await api.fetchJson<AdminMeResponse>('/admin/auth/me', {
          headers: adminHeaders(jwt),
        });
        if (cancelled) return;
        const roles = Array.isArray(body.roles) ? body.roles : [];
        const method = String(body.auth_method || '').trim();
        // Prefer real IdP mapping; ignore open/demo admin acceptance of arbitrary JWT.
        const mapped = roles.length > 0 && (method === 'oidc' || method === 'jwt');
        setIdpAdminMapped(mapped);
        if (!mapped) {
          return;
        }

        setAdminTokenState((current) => {
          const currentTrim = current.trim();
          if (currentTrim === jwt) {
            autoAdminSyncRef.current = jwt;
            return current;
          }

          // Replace shipped demo admin keys, or refresh if we already synced a prior IdP JWT.
          const replaceDemo = isReplaceableAdminToken(currentTrim);
          const refreshSyncedJwt =
            looksLikeJwt(currentTrim) && autoAdminSyncRef.current === currentTrim;

          if (!replaceDemo && !refreshSyncedJwt) {
            return current;
          }

          if (replaceDemo) {
            sessionStorage.setItem(ADMIN_BEFORE_IDP_KEY, currentTrim || 'rag-admin-demo-key');
          }
          const announce = autoAdminSyncRef.current !== jwt;
          autoAdminSyncRef.current = jwt;
          saveTokens({ adminToken: jwt });
          if (announce) {
            queueMicrotask(() =>
              toast(
                refreshSyncedJwt
                  ? 'Admin bearer updated to new IdP token.'
                  : 'Admin bearer set to IdP token (admin_role_map) — demo credibility.',
                'ok',
              ),
            );
          }
          return jwt;
        });
      } catch {
        if (!cancelled) setIdpAdminMapped(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [userToken, baseUrl, toast]);

  const adminUsesIdpToken = looksLikeJwt(adminToken) && adminToken.trim() === userToken.trim();

  const value = useMemo<AuthState>(() => {
    const api = createApiClient(baseUrl);
    return {
      adminToken,
      userToken,
      baseUrl,
      operatorTenant,
      adminRoles,
      allowedTenants,
      adminAuthMethod,
      adminUsesIdpToken,
      idpAdminMapped,
      userSubject,
      userEmail,
      userGroups,
      userAuthMethod,
      api,
      setAdminToken,
      setUserToken,
      setBaseUrl,
      setOperatorTenant,
      applyIdpTokenAsAdmin,
      signOutIdp,
      adminFetchInit: () => ({ headers: adminHeaders(adminToken) }),
      userFetchInit: () => ({ headers: userHeaders(userToken) }),
      tenantQuery: (url: string) => {
        const sep = url.includes('?') ? '&' : '?';
        return `${url}${sep}tenant_id=${encodeURIComponent(operatorTenant)}`;
      },
    };
  }, [
    adminAuthMethod,
    adminRoles,
    adminToken,
    adminUsesIdpToken,
    allowedTenants,
    applyIdpTokenAsAdmin,
    baseUrl,
    idpAdminMapped,
    operatorTenant,
    setAdminToken,
    setBaseUrl,
    setOperatorTenant,
    setUserToken,
    signOutIdp,
    userAuthMethod,
    userEmail,
    userGroups,
    userSubject,
    userToken,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
