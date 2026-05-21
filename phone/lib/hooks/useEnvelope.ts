// hooks/useEnvelope.ts (phone)

import { useCallback, useEffect, useState } from "react";
import { fetchRuntimeEnvelope, type RuntimeEnvelope } from "../services/runtime";

export interface UseEnvelopeResult {
  envelope: RuntimeEnvelope | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useEnvelope(): UseEnvelopeResult {
  const [envelope, setEnvelope] = useState<RuntimeEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const e = await fetchRuntimeEnvelope();
      setEnvelope(e);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return { envelope, loading, error, refresh };
}
