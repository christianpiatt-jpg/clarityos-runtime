// hooks/useElinsFeed.ts — daily delivered-reports feed.

import { useCallback, useEffect, useState } from "react";
import { fetchDailyFeed, type ElinsDeliveredReport } from "../services/elins";

export interface UseElinsFeedResult {
  feed: ElinsDeliveredReport[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useElinsFeed(limit = 50): UseElinsFeedResult {
  const [feed, setFeed] = useState<ElinsDeliveredReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const f = await fetchDailyFeed(limit);
      setFeed(f);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { feed, loading, error, refresh };
}
