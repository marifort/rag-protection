import { normalizeBaseUrl } from '../api/client';
import { exposeConsoleRuntime } from '../runtime/expose';

export type ToastKind = 'ok' | 'err';

export type EeRegistrationDeps = {
  registerWorkspace: (registration: {
    id: string;
    label: string;
    edition: 'ce' | 'ee';
    order?: number;
    component: import('react').ComponentType<{ active: boolean }>;
  }) => void;
  React: typeof import('react');
  useAuth: () => {
    api: {
      baseUrl: string;
      fetchJson: <T>(path: string, init?: RequestInit) => Promise<T>;
    };
    adminFetchInit: () => RequestInit;
    userFetchInit: () => RequestInit;
    adminToken: string;
    userToken: string;
    operatorTenant: string;
    adminRoles: string[];
    tenantQuery: (url: string) => string;
  };
  useToast: () => {
    toast: (message: string, kind?: ToastKind) => void;
  };
  useWorkspaceNav?: () => {
    activeWorkspaceId: string;
    navigateTo: (workspaceId: string, action?: Record<string, unknown>) => void;
    pendingAction: { workspaceId: string; action: Record<string, unknown> } | null;
    consumePendingAction: (workspaceId: string) => Record<string, unknown> | null;
  };
};

export type LoadEnterpriseUiOptions = {
  baseUrl: string;
  scriptPath?: string;
};

export type EnterpriseUiModule = {
  registerEeWorkspaces: (deps: EeRegistrationDeps) => void;
};

/**
 * Dynamically import the EE workspace bundle when enterprise is installed.
 * CE must call exposeConsoleRuntime() before loading the EE script.
 */
export async function loadEnterpriseUi(
  options: LoadEnterpriseUiOptions,
): Promise<EnterpriseUiModule | null> {
  exposeConsoleRuntime();

  const base = normalizeBaseUrl(options.baseUrl);
  const scriptPath = options.scriptPath ?? '/ui/static/ee/ee-ui.js';
  const path = scriptPath.startsWith('/') ? scriptPath : `/${scriptPath}`;

  // The EE bundle uses a stable filename (unlike CE's content-hashed assets),
  // so browsers can serve a stale copy of this dynamic import across reloads.
  // Derive a version marker from the current ETag/Last-Modified and append it
  // as a query param so a changed bundle always yields a fresh module URL.
  let version = '';
  try {
    const head = await fetch(`${base}${path}`, { method: 'HEAD', cache: 'no-store' });
    version = head.headers.get('etag') || head.headers.get('last-modified') || '';
  } catch {
    version = '';
  }
  const cacheBust = version ? `?v=${encodeURIComponent(version)}` : `?t=${Date.now()}`;
  const url = `${base}${path}${cacheBust}`;

  try {
    const module = (await import(/* @vite-ignore */ url)) as EnterpriseUiModule;
    if (typeof module.registerEeWorkspaces !== 'function') {
      throw new Error('EE bundle missing registerEeWorkspaces export');
    }
    return module;
  } catch {
    return null;
  }
}

export async function probeEnterpriseInstalled(baseUrl: string): Promise<boolean> {
  const base = normalizeBaseUrl(baseUrl);
  try {
    const response = await fetch(`${base}/health`);
    if (!response.ok) return false;
    const body = (await response.json()) as { enterprise_installed?: boolean };
    return body.enterprise_installed === true;
  } catch {
    return false;
  }
}
