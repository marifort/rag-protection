import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

export const DEFAULT_OPERATION_RESULT =
  'Run Refresh or submit a query/ingest action.';

type OperationResultContextValue = {
  lastOperation: unknown | null;
  setLastOperation: (body: unknown) => void;
};

const OperationResultContext = createContext<OperationResultContextValue | null>(null);

export function OperationResultProvider({ children }: { children: ReactNode }) {
  const [lastOperation, setLastOperation] = useState<unknown | null>(null);
  const value = useMemo(
    () => ({
      lastOperation,
      setLastOperation,
    }),
    [lastOperation],
  );
  return (
    <OperationResultContext.Provider value={value}>{children}</OperationResultContext.Provider>
  );
}

export function useOperationResult(): OperationResultContextValue {
  const ctx = useContext(OperationResultContext);
  if (!ctx) {
    throw new Error('useOperationResult must be used within OperationResultProvider');
  }
  return ctx;
}
