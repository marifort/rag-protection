export { createApiClient, fetchJson, ApiError, normalizeBaseUrl } from './api/client';
export type { ApiClient, HealthResponse } from './api/client';

export { AuthProvider, useAuth } from './auth/AuthContext';
export { adminHeaders, userHeaders, loadTokens, saveTokens, appendTenantQuery, looksLikeJwt, isStaticDemoAdminToken, isReplaceableAdminToken } from './auth/tokens';
export type { TokenStorage } from './auth/tokens';

export { AppShell } from './layout/AppShell';
export type { AppShellProps } from './layout/AppShell';
export { OperatorToolbar } from './layout/OperatorToolbar';
export type { OperatorToolbarProps } from './layout/OperatorToolbar';
export { IdpAuthControl, notifyOidcUiStatusChanged, OIDC_UI_STATUS_EVENT } from './layout/IdpAuthControl';
export type { IdpAuthControlProps } from './layout/IdpAuthControl';
export { StatsPanel } from './layout/StatsPanel';
export type { StatsPanelProps } from './layout/StatsPanel';
export { StatsRangeProvider, useStatsRange, STATS_RANGE_OPTIONS } from './layout/StatsRangeContext';
export type { StatsWindow } from './layout/StatsRangeContext';
export {
  OperationResultProvider,
  useOperationResult,
  DEFAULT_OPERATION_RESULT,
} from './layout/OperationResultContext';
export { ToastProvider, useToast } from './layout/ToastContext';
export type { ToastKind } from './layout/ToastContext';
export {
  WorkspaceNavProvider,
  useWorkspaceNav,
} from './layout/WorkspaceNavContext';
export type { WorkspacePendingAction } from './layout/WorkspaceNavContext';

export { ThemeProvider, useTheme } from './theme/ThemeProvider';
export type { ThemeMode } from './theme/ThemeProvider';

export {
  registerWorkspace,
  listWorkspaces,
  getWorkspace,
  subscribeWorkspaces,
  clearWorkspacesForTests,
} from './workspace/registry';
export type {
  Edition,
  WorkspaceDefinition,
  WorkspaceRegistration,
  WorkspaceComponentProps,
} from './workspace/registry';

export { exposeConsoleRuntime, getConsoleRuntime } from './runtime/expose';
export type { ConsoleRuntime } from './runtime/expose';

export {
  loadEnterpriseUi,
  probeEnterpriseInstalled,
} from './enterprise/loadEnterpriseUi';
export type { EnterpriseUiModule, LoadEnterpriseUiOptions, EeRegistrationDeps } from './enterprise/loadEnterpriseUi';
