export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export type FetchJsonOptions = RequestInit & {
  baseUrl?: string;
};

export function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

export async function fetchJson<T = unknown>(
  path: string,
  options: FetchJsonOptions = {},
): Promise<T> {
  const base = normalizeBaseUrl(options.baseUrl ?? '');
  const url = path.startsWith('http') ? path : `${base}${path.startsWith('/') ? path : `/${path}`}`;
  const { baseUrl: _base, ...init } = options;
  const response = await fetch(url, init);
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(detail || `HTTP ${response.status}`, response.status, body);
  }
  return body as T;
}

export type HealthResponse = {
  status: string;
  version?: string;
  documents?: number;
  store_backend?: string;
  enterprise_installed?: boolean;
  oidc_enabled?: boolean;
  /** EE: auth-code + PKCE Sign in with IdP is configured and ready */
  oidc_ui_login_available?: boolean;
  /** EE: ui_client_id + ui_redirect_uri set (may still be unavailable if oidc.enabled is false) */
  oidc_ui_login_configured?: boolean;
  audit?: {
    buffer_max?: number;
    buffer_count?: number;
    file_sink?: string | null;
    webhook_configured?: boolean;
    retention_days?: number;
  };
};

export function createApiClient(baseUrl: string) {
  const base = normalizeBaseUrl(baseUrl);
  return {
    baseUrl: base,
    fetchJson: <T>(path: string, init?: RequestInit) =>
      fetchJson<T>(path, { ...init, baseUrl: base }),
    health: () => fetchJson<HealthResponse>('/health', { baseUrl: base }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
