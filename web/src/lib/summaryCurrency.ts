// summaryCurrency — is the stored summary CURRENT for the thread it describes?
//
// ★ WHY THIS EXISTS. A thread summary is computed once and stored with a
// timestamp; the thread keeps moving. Until now the card rendered the stored
// text with no indication of whether it still described the thread — and on
// 2026-09-02 it rendered a summary that had been computed by a broken
// prompt, hours after the thread had grown past it, looking exactly as
// authoritative as a fresh one. CT-1's rule: the box glows cyan when the
// summary is current and magenta when it is not.
//
// ★★ TWO AXES, BOTH MUST HOLD (#127). "Current" means the summary was made
// at or after the thread's last change AND by the code that is running now.
// The first axis catches a thread that moved; the second catches a summary
// made by an older summarizer on a thread nobody touched since — which the
// timestamp alone would have called current, wrongly.
//
// ★ D5 — "no summary" is a DIFFERENT KIND from "stale". A thread with no
// summary has nothing to be out of date; the card does not render, and this
// returns "none" rather than pretending to a staleness it cannot measure.
//
// ★ UNITS. The vault writes updated_at in milliseconds at every site
// (threads_vault._now_ms), but older rows and other producers have carried
// seconds, and relativeTime() in the panel already normalises by magnitude.
// This does the same, so a mixed-unit pair can never read as stale by
// accident of scale.

export type SummaryCurrency = "current" | "stale" | "none";

export interface SummaryCurrencyMeta {
  summary?: string | null;
  summary_ts_ms?: number | null;
  updated_at?: number | null;
  /** #127 — the COMMIT_SHA of the code that made the summary. Absent on
   *  rows that predate the stamp; never backfilled. */
  summary_commit_sha?: string | null;
}

/** Seconds-or-milliseconds → milliseconds, by magnitude. 1e11 ms is 1973;
 *  1e11 s is the year 5138. Nothing real sits on the wrong side. */
export function toMs(ts: number | null | undefined): number | null {
  if (typeof ts !== "number" || !Number.isFinite(ts) || ts <= 0) return null;
  return ts > 1e11 ? ts : ts * 1000;
}

/** A sha, or null. "unknown" is what /health reports when COMMIT_SHA is
 *  unset on the service; it is not a sha and must never compare equal. */
export function normSha(sha: string | null | undefined): string | null {
  if (typeof sha !== "string") return null;
  const s = sha.trim().toLowerCase();
  return s && s !== "unknown" ? s : null;
}

/** First 7 characters for the caption, or "unknown". */
export function shortSha(sha: string | null | undefined): string {
  const s = normSha(sha);
  return s ? s.slice(0, 7) : "unknown";
}

/**
 * @param liveCommitSha  The sha of the code RUNNING, from /health. When this
 *   argument is supplied (the panel always supplies it), the code axis is
 *   enforced: an absent sha on either side is STALE, never current. When the
 *   argument is omitted, only the time axis is checked — the pre-#127 rule,
 *   kept for callers that have no live sha to offer. A false "current" is the
 *   only reading that hides something, so every unmeasurable case on the
 *   enforced path resolves away from it.
 */
export function summaryCurrency(
  meta: SummaryCurrencyMeta | null | undefined,
  liveCommitSha?: string | null,
): SummaryCurrency {
  if (!meta || !meta.summary) return "none";
  const summarised = toMs(meta.summary_ts_ms);
  const updated = toMs(meta.updated_at);
  // A summary with no timestamp cannot claim currency; a thread with no
  // updated_at cannot be shown to have moved. Both fall to "stale".
  if (summarised === null || updated === null) return "stale";
  if (summarised < updated) return "stale";
  if (liveCommitSha === undefined) return "current";     // time axis only
  const made = normSha(meta.summary_commit_sha);
  const live = normSha(liveCommitSha);
  if (!made || !live || made !== live) return "stale";    // code axis
  return "current";
}
