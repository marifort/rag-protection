import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

const STATS_RANGE_KEY = 'ragProtectionUiStatsRange';

export const STATS_RANGE_OPTIONS = [
  { value: '1h', label: 'Last hour', caption: 'Last hour' },
  { value: '24h', label: 'Last 24 hours', caption: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days', caption: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days', caption: 'Last 30 days' },
] as const;

export const STATS_RANGE_SECONDS: Record<string, number> = {
  '1h': 3600,
  '24h': 86400,
  '7d': 7 * 86400,
  '30d': 30 * 86400,
};

export function statsRangeLabel(range: string) {
  return STATS_RANGE_OPTIONS.find((item) => item.value === range)?.caption ?? `Stats for ${range}`;
}

function readInitialRange() {
  const saved = localStorage.getItem(STATS_RANGE_KEY);
  if (saved && STATS_RANGE_SECONDS[saved]) return saved;
  return '7d';
}

export type StatsWindow = { from_ts: number; to_ts: number; label: string; range: string };

type StatsRangeContextValue = {
  range: string;
  setRange: (range: string) => void;
  window: StatsWindow;
  /**
   * Computes a window anchored to the *current* time. Unlike `window`, this is
   * recomputed on every call, so fetches triggered by an auto-refresh tick pick
   * up events that arrived after the provider mounted. Without this, `to_ts`
   * stays frozen at mount time and recent queries never show up in the table.
   */
  getWindow: () => StatsWindow;
};

const StatsRangeContext = createContext<StatsRangeContextValue | null>(null);

export function StatsRangeProvider({ children }: { children: ReactNode }) {
  const [range, setRangeState] = useState(readInitialRange);

  const setRange = (next: string) => {
    setRangeState(next);
    localStorage.setItem(STATS_RANGE_KEY, next);
  };

  const getWindow = useCallback((): StatsWindow => {
    const now = Math.floor(Date.now() / 1000);
    const seconds = STATS_RANGE_SECONDS[range] ?? STATS_RANGE_SECONDS['7d'];
    return {
      range,
      from_ts: now - seconds,
      to_ts: now,
      label: statsRangeLabel(range).replace(/^Stats for /i, ''),
    };
  }, [range]);

  const window = useMemo(() => getWindow(), [getWindow]);

  const value = useMemo(() => ({ range, setRange, window, getWindow }), [range, window, getWindow]);
  return <StatsRangeContext.Provider value={value}>{children}</StatsRangeContext.Provider>;
}

export function useStatsRange(): StatsRangeContextValue {
  const ctx = useContext(StatsRangeContext);
  if (!ctx) {
    throw new Error('useStatsRange must be used within StatsRangeProvider');
  }
  return ctx;
}
