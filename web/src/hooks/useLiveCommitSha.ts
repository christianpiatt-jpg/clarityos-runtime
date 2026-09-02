// hooks/useLiveCommitSha.ts — the sha of the code RUNNING, from /health.
//
// #127. The summary card compares the sha that MADE a summary against the
// sha that is running now; only the backend knows the latter, and /health
// already reports it (COMMIT_SHA on the service). Fetched once per page
// boot and cached at module level, mirroring useFlags -- which also means
// the same caveat: a tab that booted before a deploy holds the OLD live
// sha until hard refresh. That reads as "stale" (made != running), never
// as a false "current", so the failure direction is the safe one.
//
// "unknown" is what /health returns when COMMIT_SHA is unset. It is not a
// sha; normSha() turns it into null, and null never compares equal.

import { useEffect, useState } from "react";
import { health } from "../lib/api";
import { normSha } from "../lib/summaryCurrency";

let cache: string | null | undefined = undefined;   // undefined = not fetched yet
let inflight: Promise<string | null> | null = null;

async function fetchOnce(): Promise<string | null> {
  if (cache !== undefined) return cache;
  if (inflight) return inflight;
  inflight = health()
    .then((r) => {
      cache = normSha((r as { commit_sha?: string }).commit_sha);
      return cache;
    })
    .catch(() => {
      cache = null;          // unreachable backend: unknown, not current
      return cache;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export interface UseLiveCommitShaResult {
  sha: string | null;
  loading: boolean;
}

export function useLiveCommitSha(): UseLiveCommitShaResult {
  const [sha, setSha] = useState<string | null>(cache ?? null);
  const [loading, setLoading] = useState(cache === undefined);

  useEffect(() => {
    let active = true;
    void fetchOnce()
      .then((s) => { if (active) setSha(s); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return { sha, loading };
}

/** Test hook: forget the cached sha. */
export function _resetLiveCommitShaForTests(): void {
  cache = undefined;
  inflight = null;
}
