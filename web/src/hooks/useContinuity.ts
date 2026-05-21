// hooks/useContinuity.ts — read /continuity/snapshot.

import { useCallback, useEffect, useState } from "react";
import { fetchContinuitySnapshot, type ContinuitySnapshot } from "../services/continuity";

export interface UseContinuityResult {
  snapshot: ContinuitySnapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useContinuity(autoRefreshMs?: number): UseContinuityResult {
  const [snapshot, setSnapshot] = useState<ContinuitySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchContinuitySnapshot();
      setSnapshot(s);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    if (!autoRefreshMs || autoRefreshMs <= 0) return;
    const id = window.setInterval(() => { void refresh(); }, autoRefreshMs);
    return () => window.clearInterval(id);
  }, [autoRefreshMs, refresh]);

  return { snapshot, loading, error, refresh };
}
