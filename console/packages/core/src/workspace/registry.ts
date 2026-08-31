import type { ComponentType } from 'react';

export type Edition = 'ce' | 'ee';

export type WorkspaceDefinition = {
  id: string;
  label: string;
  edition: Edition;
  order?: number;
};

export type WorkspaceComponentProps = {
  active: boolean;
  refreshTick?: number;
};

export type WorkspaceRegistration = WorkspaceDefinition & {
  component: ComponentType<WorkspaceComponentProps>;
};

const workspaces = new Map<string, WorkspaceRegistration>();
const listeners = new Set<() => void>();

function notifyWorkspaceListeners(): void {
  listeners.forEach((listener) => listener());
}

export function subscribeWorkspaces(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function registerWorkspace(registration: WorkspaceRegistration): void {
  workspaces.set(registration.id, registration);
  notifyWorkspaceListeners();
}

export function listWorkspaces(edition?: Edition): WorkspaceRegistration[] {
  const items = [...workspaces.values()];
  const filtered = edition ? items.filter((w) => w.edition === edition) : items;
  return filtered.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

export function getWorkspace(id: string): WorkspaceRegistration | undefined {
  return workspaces.get(id);
}

export function clearWorkspacesForTests(): void {
  workspaces.clear();
  listeners.clear();
}
