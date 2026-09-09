/**
 * #161 -- three wire readers the web has and the phone lacked.
 *   normSha / shortSha  the sha fence (web lib/summaryCurrency.ts): "unknown"
 *                       is what /health reports without COMMIT_SHA -- not a
 *                       sha, never compares equal.
 *   stopMark            the stop mark (web lib/bearings.ts): #196 -- reads
 *                       the backend vocabulary's class, not the raw token.
 *                       Only "cut" marks. The thread wire still sends
 *                       neither field, so nothing marks on this surface
 *                       today -- no producer was added.
 */
export function normSha(sha: string | null | undefined): string | null {
  if (typeof sha !== "string") return null;
  const s = sha.trim().toLowerCase();
  return s && s !== "unknown" ? s : null;
}

export function shortSha(sha: string | null | undefined): string {
  const s = normSha(sha);
  return s ? s.slice(0, 7) : "unknown";
}

/** #196 (CT-1 2026-09-09) -- the stop mark, read from the ONE backend
 *  vocabulary (stop_vocabulary.py) and never from the raw token. The
 *  class is "normal" | "cut" | "unknown"; ONLY "cut" earns a mark.
 *  "unknown" renders NOTHING -- it is not a cut and not a completion,
 *  and the backend has already logged the word once. Absent class (a
 *  mock, a provider that sends no signal, an older wire) renders
 *  nothing too. The RAW vendor token is what the mark NAMES (R5.3),
 *  so "stopped early: max_tokens" still says which instrument spoke. */
export type StopClass = "normal" | "cut" | "unknown";

export function stopMark(stopReason: unknown, stopClass: unknown): string | null {
  if (stopClass !== "cut") return null;
  if (typeof stopReason !== "string" || !stopReason.trim()) return null;
  return stopReason.trim();
}
