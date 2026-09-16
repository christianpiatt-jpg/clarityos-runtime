/**
 * #161a -- the sha of the code RUNNING, read ONCE per app boot (the web and
 * desktop hooks/useLiveCommitSha): a module cache and an in-flight guard, so
 * every thread screen shares one /health read instead of one per mount. A
 * screen that booted before a deploy holds the OLD live sha until relaunch,
 * which reads as stale (made != running), never as a false "current".
 *
 * The fetcher is passed in (lib/api.health) so this module stays pure for
 * the node test runner. An unreachable backend caches null -- "unknown", and
 * normSha's null never compares equal to a made-sha.
 */
import { normSha } from "./wire";

export type LiveShaFetcher = () => Promise<{ commit_sha?: string | null }>;

let cache: string | null | undefined = undefined;   // undefined = not fetched yet
let inflight: Promise<string | null> | null = null;

export function liveShaOnce(fetcher: LiveShaFetcher): Promise<string | null> {
  if (cache !== undefined) return Promise.resolve(cache);
  if (inflight) return inflight;
  inflight = fetcher()
    .then((r) => {
      cache = normSha(r.commit_sha);
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

/** Test hook: forget the cached sha. */
export function _resetLiveShaForTests(): void {
  cache = undefined;
  inflight = null;
}
