import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type WorkspacePendingAction = {
  workspaceId: string;
  action: Record<string, unknown>;
};

type WorkspaceNavContextValue = {
  activeWorkspaceId: string;
  navigateTo: (workspaceId: string, action?: Record<string, unknown>) => void;
  pendingAction: WorkspacePendingAction | null;
  consumePendingAction: (workspaceId: string) => Record<string, unknown> | null;
};

const WorkspaceNavContext = createContext<WorkspaceNavContextValue | null>(null);

export type WorkspaceNavProviderProps = {
  activeWorkspaceId: string;
  onActiveWorkspaceChange: (workspaceId: string) => void;
  children: ReactNode;
};

export function WorkspaceNavProvider({
  activeWorkspaceId,
  onActiveWorkspaceChange,
  children,
}: WorkspaceNavProviderProps) {
  const [pendingAction, setPendingAction] = useState<WorkspacePendingAction | null>(null);

  const navigateTo = useCallback(
    (workspaceId: string, action?: Record<string, unknown>) => {
      onActiveWorkspaceChange(workspaceId);
      if (action) {
        setPendingAction({ workspaceId, action });
      }
    },
    [onActiveWorkspaceChange],
  );

  const consumePendingAction = useCallback(
    (workspaceId: string) => {
      if (!pendingAction || pendingAction.workspaceId !== workspaceId) return null;
      const action = pendingAction.action;
      setPendingAction(null);
      return action;
    },
    [pendingAction],
  );

  const value = useMemo(
    () => ({
      activeWorkspaceId,
      navigateTo,
      pendingAction,
      consumePendingAction,
    }),
    [activeWorkspaceId, consumePendingAction, navigateTo, pendingAction],
  );

  return <WorkspaceNavContext.Provider value={value}>{children}</WorkspaceNavContext.Provider>;
}

export function useWorkspaceNav(): WorkspaceNavContextValue {
  const ctx = useContext(WorkspaceNavContext);
  if (!ctx) {
    throw new Error('useWorkspaceNav must be used within WorkspaceNavProvider');
  }
  return ctx;
}
