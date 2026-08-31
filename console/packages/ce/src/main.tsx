import '../../core/src/theme/tokens.css';

import { useCallback } from 'react';

import {
  ApiError,
  AppShell,
  AuthProvider,
  OperationResultProvider,
  StatsRangeProvider,
  ThemeProvider,
  ToastProvider,
  registerWorkspace,
  useAuth,
  useOperationResult,
  useToast,
} from '@rag-protection/console-core';
import { createRoot } from 'react-dom/client';

import { RefreshProvider, useRefresh } from './refresh/RefreshContext';
import { AuditLogPane } from './workspaces/AuditLogPane';
import { DocumentsIngestPane } from './workspaces/DocumentsIngestPane';
import { OverviewPane } from './workspaces/OverviewPane';
import { QueryLabPane } from './workspaces/QueryLabPane';
import { ToolGatewayPane } from './workspaces/ToolGatewayPane';

registerWorkspace({
  id: 'overview',
  label: 'Overview',
  edition: 'ce',
  order: 0,
  component: OverviewPane,
});

registerWorkspace({
  id: 'query',
  label: 'Query Lab',
  edition: 'ce',
  order: 1,
  component: QueryLabPane,
});

registerWorkspace({
  id: 'documents',
  label: 'Documents & Ingest',
  edition: 'ce',
  order: 2,
  component: DocumentsIngestPane,
});

registerWorkspace({
  id: 'tools',
  label: 'Tool Gateway',
  edition: 'ce',
  order: 3,
  component: ToolGatewayPane,
});

registerWorkspace({
  id: 'audit',
  label: 'Audit Log',
  edition: 'ce',
  order: 4,
  component: AuditLogPane,
});

function defaultBaseUrl() {
  const { origin, pathname } = window.location;
  const stripped = pathname.replace(/\/ui\/?$/i, '').replace(/\/+$/, '');
  return origin + stripped;
}

// CE-only debug override: `?ee=off` on the URL or VITE_EE=off in the dev env
// skips the Enterprise probe so the shell renders CE workspaces only, even when
// the proxy reports enterprise_installed: true.
function enterpriseBootstrapEnabled() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('ee') === 'off') return false;
  if (import.meta.env.VITE_EE === 'off') return false;
  return true;
}

function CeApp() {
  const { bump, tick, autoRefresh, setAutoRefresh } = useRefresh();
  const { api, adminToken, adminFetchInit, tenantQuery } = useAuth();
  const { setLastOperation } = useOperationResult();
  const { toast } = useToast();
  const baseUrl = defaultBaseUrl();

  const handleRefresh = useCallback(async () => {
    bump();
    const jobs: Promise<unknown>[] = [api.health(), fetch(api.baseUrl + '/metrics').then((r) => r.text())];
    if (adminToken) {
      jobs.push(
        api
          .fetchJson(tenantQuery('/admin/overview/stats?from_ts=0&to_ts=1'), adminFetchInit())
          .catch(() => null),
      );
    }
    const results = await Promise.allSettled(jobs);
    const failures = results.filter((result) => result.status === 'rejected');
    if (failures.length) {
      const first = failures[0];
      const reason = first.status === 'rejected' ? first.reason : null;
      if (reason instanceof ApiError && (reason.status === 401 || reason.status === 403)) {
        const message = 'Unauthorized for one or more panels. Check admin/user bearer tokens.';
        setLastOperation({
          status: 'error',
          detail: message,
        });
        toast(message, 'err');
      } else {
        const message =
          reason instanceof Error ? reason.message : String(reason ?? 'Refresh failed');
        setLastOperation({ status: 'error', detail: message });
        toast(message, 'err');
      }
      return;
    }
    setLastOperation({ status: 'ok', refreshed_at: new Date().toISOString() });
  }, [adminFetchInit, adminToken, api, bump, setLastOperation, tenantQuery, toast]);

  return (
    <AppShell
      bare
      title="Marifort Gate"
      defaultBaseUrl={baseUrl}
      edition="ce"
      bootstrapEnterprise={enterpriseBootstrapEnabled()}
      onRefresh={handleRefresh}
      onSilentRefresh={bump}
      refreshTick={tick}
      autoRefresh={autoRefresh}
      onAutoRefreshChange={setAutoRefresh}
    />
  );
}

const root = document.getElementById('root');
if (root) {
  const baseUrl = defaultBaseUrl();
  createRoot(root).render(
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider defaultBaseUrl={baseUrl}>
          <StatsRangeProvider>
            <OperationResultProvider>
              <RefreshProvider>
                <CeApp />
              </RefreshProvider>
            </OperationResultProvider>
          </StatsRangeProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>,
  );
}
