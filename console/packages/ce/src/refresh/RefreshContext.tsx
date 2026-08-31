import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

type RefreshContextValue = {
  tick: number;
  bump: () => void;
  autoRefresh: boolean;
  setAutoRefresh: (enabled: boolean) => void;
};

const RefreshContext = createContext<RefreshContextValue | null>(null);

export function RefreshProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => {
      setTick((current) => current + 1);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [autoRefresh]);

  const value = useMemo(
    () => ({
      tick,
      bump: () => setTick((current) => current + 1),
      autoRefresh,
      setAutoRefresh,
    }),
    [autoRefresh, tick],
  );
  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>;
}

export function useRefresh(): RefreshContextValue {
  const ctx = useContext(RefreshContext);
  if (!ctx) {
    throw new Error('useRefresh must be used within RefreshProvider');
  }
  return ctx;
}
