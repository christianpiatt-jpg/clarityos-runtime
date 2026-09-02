// summaryCurrency — is the stored summary CURRENT for the thread it describes?
//
// ★ WHY THIS EXISTS. A thread summary is computed once and stored with a
// timestamp; the thread keeps moving. Until now the card rendered the stored
// text with no indication of whether it still described the thread — and on
// 2026-09-02 it rendered a summary that had been computed by a broken
// prompt, hours after the thread had grown past it, looking exactly as
// authoritative as a fresh one. CT-1's rule: the box glows cyan when the
// summary is current and magenta when it is not. The state is DERIVED from
// two timestamps the meta already carries; nothing new is stored.
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
}

/** Seconds-or-milliseconds → milliseconds, by magnitude. 1e11 ms is 1973;
 *  1e11 s is the year 5138. Nothing real sits on the wrong side. */
export function toMs(ts: number | null | undefined): number | null {
  if (typeof ts !== "number" || !Number.isFinite(ts) || ts <= 0) return null;
  return ts > 1e11 ? ts : ts * 1000;
}

export function summaryCurrency(meta: SummaryCurrencyMeta | null | undefined): SummaryCurrency {
  if (!meta || !meta.summary) return "none";
  const summarised = toMs(meta.summary_ts_ms);
  const updated = toMs(meta.updated_at);
  // A summary with no timestamp cannot claim currency; a thread with no
  // updated_at cannot be shown to have moved. Both fall to "stale" rather
  // than "current": the only reading that can be WRONG in a way that hides
  // something is a false "current".
  if (summarised === null || updated === null) return "stale";
  return summarised >= updated ? "current" : "stale";
}
