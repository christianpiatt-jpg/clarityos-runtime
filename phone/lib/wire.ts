/**
 * #161 -- three wire readers the web has and the phone lacked.
 *   normSha / shortSha  the sha fence (web lib/summaryCurrency.ts): "unknown"
 *                       is what /health reports without COMMIT_SHA -- not a
 *                       sha, never compares equal.
 *   stopMark            the stop mark (web lib/bearings.ts): a provider stop
 *                       signal other than end_turn means the reply was cut
 *                       off; null / absent is a mock or an unknown stop --
 *                       no mark, no sentinel.
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

export function stopMark(stopReason: unknown): string | null {
  if (typeof stopReason !== "string" || !stopReason.trim()) return null;
  return stopReason === "end_turn" ? null : stopReason;
}
