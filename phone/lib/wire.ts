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

// ---------------------------------------------------------------------------
// #161a -- the sha FENCE as the web renders it (web/src/lib/summaryCurrency.ts):
// is a stored summary CURRENT for the thread it describes? Two axes, no
// clock: the TURN it was made at (meta.summary_turn vs meta.message_count)
// and the SHA that made it (meta.summary_commit_sha vs the sha running).
// Both hold -> "fresh"; one broke -> "aged"; neither, or no stamp -> "old".
// "none" when there is no summary at all (a different KIND from old).
// ---------------------------------------------------------------------------
export type Currency = "fresh" | "aged" | "old";
export type SummaryCurrency = Currency | "none";

export interface CurrencyStamps {
  made_turn?: number | null;
  now_turn?: number | null;
  made_sha?: string | null;
  live_sha?: string | null;
}

export interface SummaryCurrencyMeta {
  summary?: string | null;
  summary_turn?: number | null;
  message_count?: number | null;
  summary_commit_sha?: string | null;
}

/** A turn stamp, or null: a non-negative integer and nothing else. */
export function normTurn(t: number | null | undefined): number | null {
  return typeof t === "number" && Number.isInteger(t) && t >= 0 ? t : null;
}

/** The ONE verdict (#190 on the web). No clock. */
export function readCurrency(stamps: CurrencyStamps | null | undefined): Currency {
  const s = stamps ?? {};
  const made = normTurn(s.made_turn);
  if (made === null) return "old";   // no stamp -> old, whatever the sha says
  const now = normTurn(s.now_turn);
  const turnOk = now !== null && made === now;
  const madeSha = normSha(s.made_sha);
  const liveSha = normSha(s.live_sha);
  const shaOk = madeSha !== null && liveSha !== null && madeSha === liveSha;
  if (turnOk && shaOk) return "fresh";
  if (turnOk || shaOk) return "aged";
  return "old";
}

export function summaryCurrency(
  meta: SummaryCurrencyMeta | null | undefined,
  liveCommitSha?: string | null,
): SummaryCurrency {
  if (!meta || !meta.summary) return "none";
  return readCurrency({
    made_turn: meta.summary_turn,
    now_turn: meta.message_count,
    made_sha: meta.summary_commit_sha,
    live_sha: liveCommitSha,
  });
}

/** #219 on the web -- absence names its reason, in one sentence. */
export const UNSTAMPED_CAPTION = "not stamped — summarized before the stamp shipped";

export function turnCaption(stamps: CurrencyStamps | null | undefined): string {
  const s = stamps ?? {};
  const made = normTurn(s.made_turn);
  if (made === null) return UNSTAMPED_CAPTION;
  const now = normTurn(s.now_turn);
  return `made turn ${made} · now turn ${now === null ? "—" : now}`;
}

// ---------------------------------------------------------------------------
// #151 -- the word the home screen's cloud probe shows for a failed /health:
// a 401 is "not signed in", a 403 "not permitted", any other status names
// itself ("HTTP <n>") and never the server's message string (a server body is
// not a client word); no status at all -- the backend could not be reached --
// is "unreachable". (/health is probed without a session, so the two auth
// words are reachable only if that changes.)
// ---------------------------------------------------------------------------
export function healthWord(status: unknown): string {
  const n = typeof status === "number" && Number.isFinite(status) ? status : 0;
  if (n === 401) return "not signed in";
  if (n === 403) return "not permitted";
  if (n > 0) return `HTTP ${n}`;
  return "unreachable";
}
