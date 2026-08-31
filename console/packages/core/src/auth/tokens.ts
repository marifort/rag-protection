export type TokenStorage = {
  adminToken: string;
  userToken: string;
  baseUrl: string;
  operatorTenant: string;
};

// Match legacy index.html keys so tokens carry over during migration.
const ADMIN_KEY = 'ragProtectionUiAdminToken';
const USER_KEY = 'ragProtectionUiUserToken';
const BASE_KEY = 'ragProtectionUiBaseUrl';
const OPERATOR_TENANT_KEY = 'ragProtectionUiOperatorTenant';
/** IdP email from Sign-in ticket / id_token — access JWTs often omit email. */
const USER_EMAIL_KEY = 'ragProtectionUiIdpEmail';
const USER_EMAIL_FOR_TOKEN_KEY = 'ragProtectionUiIdpEmailForToken';

/** Stash static demo admin key while IdP JWT is used as Admin bearer (demo credibility). */
export const ADMIN_BEFORE_IDP_KEY = 'ragProtectionAdminBeforeIdp';

const STATIC_DEMO_ADMIN_TOKENS = new Set([
  'rag-admin-demo-key',
  'rag-audit-reader-key',
  'rag-audit-debug-key',
  'rag-ingest-admin-key',
  'rag-policy-admin-key',
  'acme-ingest-admin',
  'globex-audit-reader',
]);

/** Toolbar placeholder / env-var name — not a real admin secret. */
const ADMIN_PLACEHOLDER_TOKENS = new Set(['RAG_ADMIN_API_KEY']);

export function looksLikeJwt(token: string): boolean {
  const value = token.trim();
  if (value.length < 40) return false;
  const parts = value.split('.');
  return parts.length === 3 && parts.every((part) => part.length > 0);
}

/** True when the admin field holds a shipped demo/static key safe to replace with an IdP JWT. */
export function isStaticDemoAdminToken(token: string): boolean {
  const value = token.trim();
  if (!value || looksLikeJwt(value)) return false;
  return STATIC_DEMO_ADMIN_TOKENS.has(value);
}

/**
 * True when Admin bearer is empty, a placeholder, or a shipped demo key —
 * safe to replace with the IdP access token on Sign in.
 */
export function isReplaceableAdminToken(token: string): boolean {
  const value = token.trim();
  if (!value || ADMIN_PLACEHOLDER_TOKENS.has(value)) return true;
  return isStaticDemoAdminToken(value);
}

export function loadTokens(defaultBaseUrl = ''): TokenStorage {
  return {
    adminToken: localStorage.getItem(ADMIN_KEY) ?? 'rag-admin-demo-key',
    userToken: localStorage.getItem(USER_KEY) ?? 'employee-demo-token',
    baseUrl: localStorage.getItem(BASE_KEY) ?? defaultBaseUrl,
    operatorTenant: localStorage.getItem(OPERATOR_TENANT_KEY) ?? 'default',
  };
}

export function saveTokens(tokens: Partial<TokenStorage>): void {
  if (tokens.adminToken !== undefined) {
    localStorage.setItem(ADMIN_KEY, tokens.adminToken);
  }
  if (tokens.userToken !== undefined) {
    localStorage.setItem(USER_KEY, tokens.userToken);
  }
  if (tokens.baseUrl !== undefined) {
    localStorage.setItem(BASE_KEY, tokens.baseUrl);
  }
  if (tokens.operatorTenant !== undefined) {
    localStorage.setItem(OPERATOR_TENANT_KEY, tokens.operatorTenant);
  }
}

/**
 * Restore IdP display email after reload when the stored JWT still matches.
 * Auth0 access tokens often omit email; Sign-in puts it on the ticket only.
 */
export function loadPersistedIdpEmail(userToken: string): string {
  const token = userToken.trim();
  if (!looksLikeJwt(token)) return '';
  if (localStorage.getItem(USER_EMAIL_FOR_TOKEN_KEY) === token) {
    const stored = (localStorage.getItem(USER_EMAIL_KEY) || '').trim();
    if (stored) return stored;
  }
  // Same-tab reload: ticket cache in sessionStorage may still hold id_token email.
  const fromTicket = findEmailInOidcTicketCache(token);
  if (fromTicket) {
    persistIdpEmail(token, fromTicket);
    return fromTicket;
  }
  return '';
}

function findEmailInOidcTicketCache(userToken: string): string {
  if (typeof sessionStorage === 'undefined') return '';
  const token = userToken.trim();
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (!key || !key.startsWith('ragProtectionOidcTicket:')) continue;
    const raw = sessionStorage.getItem(key);
    if (!raw) continue;
    try {
      const parsed = JSON.parse(raw) as { token?: string; email?: string };
      if (parsed.token === token && parsed.email) {
        return String(parsed.email).trim();
      }
    } catch {
      // Legacy raw-token cache — no email.
    }
  }
  return '';
}

export function persistIdpEmail(userToken: string, email: string): void {
  const token = userToken.trim();
  const value = email.trim();
  if (!looksLikeJwt(token) || !value) {
    clearPersistedIdpEmail();
    return;
  }
  localStorage.setItem(USER_EMAIL_KEY, value);
  localStorage.setItem(USER_EMAIL_FOR_TOKEN_KEY, token);
}

export function clearPersistedIdpEmail(): void {
  localStorage.removeItem(USER_EMAIL_KEY);
  localStorage.removeItem(USER_EMAIL_FOR_TOKEN_KEY);
}

export function appendTenantQuery(url: string, tenantId: string): string {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}tenant_id=${encodeURIComponent(tenantId)}`;
}

export function adminHeaders(adminToken: string): HeadersInit {
  if (!adminToken) return {};
  return { Authorization: `Bearer ${adminToken}` };
}

export function userHeaders(userToken: string): HeadersInit {
  if (!userToken) return {};
  return { Authorization: `Bearer ${userToken}` };
}
