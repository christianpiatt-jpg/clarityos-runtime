// phone/lib/hooks/useFlags.ts — pull /v29/flags + cache to AsyncStorage so
// offline launches still know whether v28 surfaces are enabled.

import { useCallback, useEffect, useState } from "react";
import { v29Flags, type V29Flag } from "../api";
import { storage } from "../storage";

const FLAGS_CACHE_KEY = "clarityos.v29_flags";

type FlagMap = Partial<Record<V29Flag, boolean>>;

let cache: FlagMap | null = null;

async function loadCachedFlags(): Promise<FlagMap | null> {
  try {
    const raw = await storage.get(FLAGS_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as FlagMap;
  } catch {
    // Corrupted cache — silently drop and refetch.
  }
  return null;
}

async function persistFlags(flags: FlagMap): Promise<void> {
  try {
    await storage.set(FLAGS_CACHE_KEY, JSON.stringify(flags));
  } catch {
    // Best effort.
  }
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
    try {
      const r = await v29Flags();
      cache = r.flags;
      setFlags(r.flags);
      await persistFlags(r.flags);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      // Render whatever we have cached (synchronous) → fetch fresh in
      // background. Offline launches still see a useful flag map.
      if (!cache) {
        const cached = await loadCachedFlags();
        if (cached && active) {
          cache = cached;
          setFlags(cached);
        }
      }
      try {
        const r = await v29Flags();
        if (!active) return;
        cache = r.flags;
        setFlags(r.flags);
        await persistFlags(r.flags);
      } catch (e: unknown) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  return { flags, loading, error, refresh };
}
