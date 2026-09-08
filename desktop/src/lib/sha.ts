/**
 * #167b -- the sha fence (the web's lib/summaryCurrency.ts normSha /
 * shortSha). "unknown" is what /health reports when COMMIT_SHA is unset on
 * the service; it is not a sha and must never compare equal.
 */
export function normSha(sha: string | null | undefined): string | null {
  if (typeof sha !== "string") return null;
  const s = sha.trim().toLowerCase();
  return s && s !== "unknown" ? s : null;
}

/** First 7 characters for a caption, or "unknown". */
export function shortSha(sha: string | null | undefined): string {
  const s = normSha(sha);
  return s ? s.slice(0, 7) : "unknown";
}
