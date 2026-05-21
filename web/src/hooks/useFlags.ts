// hooks/useFlags.ts — pull /v29/flags once per session and cache.
//
// Cockpit + Elins both consult this; we don't want to hit /v29/flags from
// every component. The hook keeps a module-level cache so multiple consumers
// share one in-flight request and one resolution.

import { useCallback, useEffect, useState } from "react";
import { ApiError, v29Flags, type V29Flag } from "../lib/api";

type FlagMap = Partial<Record<V29Flag, boolean>>;

let cache: FlagMap | null = null;
let inflight: Promise<FlagMap> | null = null;

async function fetchOnce(): Promise<FlagMap> {
  if (cache) return cache;
  if (inflight) return inflight;
  inflight = v29Flags()
    .then((r) => {
      cache = r.flags;
      return cache;
    })
    .catch((e) => {
      // Default to all-false on failure — v28 surfaces stay hidden until we
      // know they're enabled. This biases toward conservative rollout.
      if (e instanceof ApiError && e.code === "missing_session") {
        return {};
      }
      cache = {};
      return cache;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export interface UseFlagsResult {
  flags: FlagMap;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useFlags(): UseFlagsResult {
  const [flags, setFlags] = useState<FlagMap>(cache ?? {});
  const [loading, setLoading] = useState(!cache);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    cache = null;          // invalidate
    inflight = null;
    try {
      const f = await fetchOnce();
      setFlags(f);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void fetchOnce()
      .then((f) => { if (active) setFlags(f); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return { flags, loading, error, refresh };
}

export function flagEnabled(flags: FlagMap, name: V29Flag): boolean {
  return flags[name] === true;
}
