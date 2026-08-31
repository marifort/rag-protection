import * as React from 'react';
import { render, type RenderResult } from '@testing-library/react';

import {
  AuthProvider,
  OperationResultProvider,
  StatsRangeProvider,
  ToastProvider,
  WorkspaceNavProvider,
} from '@rag-protection/console-core';

import { RefreshProvider } from '../refresh/RefreshContext';

type PaneProps = { active: boolean; refreshTick?: number };

export function renderCePane(
  Pane: React.ComponentType<PaneProps>,
  options: {
    baseUrl?: string;
    adminToken?: string;
    userToken?: string;
    onWorkspaceChange?: (id: string) => void;
    activeWorkspaceId?: string;
  } = {},
): RenderResult {
  const {
    baseUrl = 'http://localhost:8090',
    adminToken = '',
    userToken = 'employee-demo-token',
    onWorkspaceChange = () => undefined,
    activeWorkspaceId = 'query',
  } = options;

  if (adminToken !== undefined) {
    window.localStorage.setItem('ragProtectionUiAdminToken', adminToken);
  }
  if (userToken !== undefined) {
    window.localStorage.setItem('ragProtectionUiUserToken', userToken);
  }
  window.localStorage.setItem('ragProtectionUiBaseUrl', baseUrl);

  return render(
    <ToastProvider>
      <AuthProvider defaultBaseUrl={baseUrl}>
        <StatsRangeProvider>
          <OperationResultProvider>
            <RefreshProvider>
              <WorkspaceNavProvider
                activeWorkspaceId={activeWorkspaceId}
                onActiveWorkspaceChange={onWorkspaceChange}
              >
                <Pane active />
              </WorkspaceNavProvider>
            </RefreshProvider>
          </OperationResultProvider>
        </StatsRangeProvider>
      </AuthProvider>
    </ToastProvider>,
  );
}
