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
