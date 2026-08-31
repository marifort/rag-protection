import { useEffect, useMemo, useState, type ReactNode } from 'react';

import { AuthProvider, useAuth } from '../auth/AuthContext';
import { ThemeProvider, useTheme } from '../theme/ThemeProvider';
import { useEnterpriseEdition } from '../enterprise/EnterpriseBootstrap';
import { IdpAuthControl } from './IdpAuthControl';
import { OperatorToolbar } from './OperatorToolbar';
import { StatsPanel } from './StatsPanel';
import { StatsRangeProvider } from './StatsRangeContext';
import { OperationResultProvider } from './OperationResultContext';
import { ToastProvider } from './ToastContext';
import { WorkspaceNavProvider } from './WorkspaceNavContext';
import { listWorkspaces, subscribeWorkspaces, type WorkspaceRegistration } from '../workspace/registry';
import type { HealthResponse } from '../api/client';

export type AppShellProps = {
  title?: string;
  subtitle?: string;
  defaultBaseUrl?: string;
  edition?: 'ce' | 'ee' | 'all';
  bootstrapEnterprise?: boolean;
  headerExtra?: ReactNode;
  onRefresh?: () => void | Promise<void>;
  onSilentRefresh?: () => void;
  refreshTick?: number;
  autoRefresh?: boolean;
  onAutoRefreshChange?: (enabled: boolean) => void;
  /** When true, shell assumes providers are mounted by the caller. */
  bare?: boolean;
};

function HeroBadges({ refreshTick = 0 }: { refreshTick?: number }) {
  const { api } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const body = await api.health();
        if (!cancelled) setHealth(body);
      } catch {
        if (!cancelled) setHealth(null);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [api, refreshTick]);

  const healthy = health?.status === 'healthy';
  const store = health?.store_backend || 'loading';

  return (
    <>
      <div
        className="badge"
        style={{
          borderColor: store === 'hybrid' ? 'rgba(125,211,252,0.55)' : undefined,
        }}
      >
        store: {store}
      </div>
      <div
        className="badge"
        style={{
          borderColor: health ? (healthy ? 'rgba(52,211,153,0.45)' : 'rgba(248,113,113,0.45)') : undefined,
          color: health ? (healthy ? 'var(--health-ok-text)' : 'var(--toast-err-text)') : undefined,
        }}
      >
        health: {health ? (healthy ? 'healthy' : 'degraded') : 'loading'}
      </div>
      <a href="/docs" target="_blank" rel="noreferrer" className="badge" style={{ textDecoration: 'none', color: 'inherit' }}>
        API Docs ↗
      </a>
    </>
  );
}

function ShellBody({
  title,
  subtitle,
  edition: editionProp = 'all',
  bootstrapEnterprise = false,
  defaultBaseUrl = '',
  headerExtra,
  onRefresh,
  onSilentRefresh,
  refreshTick = 0,
  autoRefresh = false,
  onAutoRefreshChange,
}: Omit<AppShellProps, 'defaultBaseUrl'> & { defaultBaseUrl?: string }) {
  const { mode, setMode } = useTheme();
  const { edition, bootstrap } = useEnterpriseEdition({
    initialEdition: editionProp,
    bootstrapEnterprise,
    baseUrl: defaultBaseUrl,
  });
  const [registryTick, setRegistryTick] = useState(0);

  useEffect(() => subscribeWorkspaces(() => setRegistryTick((tick) => tick + 1)), []);

  const workspaces = useMemo(() => {
    if (edition === 'all') return listWorkspaces();
    return listWorkspaces(edition);
  }, [edition, registryTick]);
  const [activeId, setActiveId] = useState(() => {
    if (typeof window !== 'undefined') {
      const fromUrl = new URLSearchParams(window.location.search).get('workspace');
      if (fromUrl) return fromUrl;
    }
    return workspaces[0]?.id ?? '';
  });

  useEffect(() => {
    setActiveId((current) => {
      if (current && workspaces.some((workspace) => workspace.id === current)) {
        return current;
      }
      if (typeof window !== 'undefined') {
        const fromUrl = new URLSearchParams(window.location.search).get('workspace');
        if (fromUrl && workspaces.some((workspace) => workspace.id === fromUrl)) {
          return fromUrl;
        }
      }
      return workspaces[0]?.id ?? '';
    });
  }, [workspaces]);

  const active = workspaces.find((w) => w.id === activeId) ?? workspaces[0];

  const description =
    subtitle ??
    'ACL gateway for RAG — retrieval ACL, DLP scanning, injection shielding, citation auditing, document ingest, and policy inspection.';

  return (
    <div className="page">
      <div className="hero">
        <div>
          <div className="hero-brand">
            <img className="hero-logo" src="/ui/static/logo-mark.svg" width="52" height="52" alt="" />
            <div className="hero-title-block">
              <h1>{title ?? 'Marifort Gate'}</h1>
              <p className="hero-byline">ACL gateway for RAG</p>
            </div>
          </div>
          <p>{description}</p>
        </div>
        <div className="hero-right">
          <label className="toggle">
            <input
              type="checkbox"
              checked={mode === 'light'}
              onChange={(event) => setMode(event.target.checked ? 'light' : 'dark')}
            />
            Light theme
          </label>
          {onAutoRefreshChange ? (
            <label className="toggle">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(event) => onAutoRefreshChange(event.target.checked)}
              />
              Auto refresh (5s)
            </label>
          ) : null}
          <HeroBadges refreshTick={refreshTick} />
          {headerExtra}
          <IdpAuthControl refreshTick={refreshTick} />
        </div>
      </div>

      <OperatorToolbar onRefresh={onRefresh} onTenantChange={onSilentRefresh} />
      {bootstrap}

      <div className="workspace-shell">
        <aside className="workspace-nav" aria-label="Workspaces">
          <h3>Workspace</h3>
          {workspaces.map((workspace: WorkspaceRegistration) => (
            <button
              key={workspace.id}
              type="button"
              className={`workspace-btn${workspace.id === active?.id ? ' active' : ''}`}
              onClick={() => setActiveId(workspace.id)}
            >
              {workspace.label}
            </button>
          ))}
          {!workspaces.length ? <p className="muted" style={{ margin: 0 }}>No workspaces registered yet.</p> : null}
        </aside>

        <div className="workspace-stage">
          <StatsPanel refreshTick={refreshTick} />
          <WorkspaceNavProvider activeWorkspaceId={active?.id ?? ''} onActiveWorkspaceChange={setActiveId}>
            {active ? (
              <div className="workspace-pane active">
                <active.component active refreshTick={refreshTick} />
              </div>
            ) : null}
          </WorkspaceNavProvider>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ defaultBaseUrl, bare = false, ...rest }: AppShellProps) {
  const body = <ShellBody defaultBaseUrl={defaultBaseUrl} {...rest} />;
  if (bare) return body;
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider defaultBaseUrl={defaultBaseUrl}>
          <StatsRangeProvider>
            <OperationResultProvider>{body}</OperationResultProvider>
          </StatsRangeProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
