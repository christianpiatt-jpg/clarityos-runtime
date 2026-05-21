// hooks/useContinuity.ts (phone)

import { useCallback, useEffect, useState } from "react";
import { fetchContinuitySnapshot, type ContinuitySnapshot } from "../services/continuity";

export interface UseContinuityResult {
  snapshot: ContinuitySnapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useContinuity(): UseContinuityResult {
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
  return { snapshot, loading, error, refresh };
}
