// summaryCurrency — is a stored reading CURRENT for the thread it describes?
//
// ★ WHY THIS EXISTS. A thread summary is computed once and stored; the
// thread keeps moving. On 2026-09-02 the card rendered a summary made by a
// broken prompt, hours after the thread had grown past it, looking exactly
// as authoritative as a fresh one. The box says whether the reading still
// describes the thread.
//
// ★★ #190 (CT-1 2026-09-08) -- TWO AXES, BOTH MUST HOLD, AND NO CLOCK.
//   turn axis  the reading was made at the thread's CURRENT turn
//              (made_turn === now_turn; now = meta.message_count, made =
//              meta.summary_turn, the #139 passenger stamp).
//   sha axis   the reading was made by the code that is running now
//              (normSha equal).
// Both hold -> "fresh" (green). One broke -> "aged" (yellow). Both broke, or
// no stamp at all -> "old" (magenta). The old verdict compared timestamps
// (summary_ts_ms against updated_at, scaled by magnitude) -- a clock; age is
// TURNS. toMs stays exported for callers that format a stamp; it no longer
// touches the verdict.
//
// ★ D5 — "no summary" is a DIFFERENT KIND from "old". A thread with no
// summary has nothing to be out of date; the card does not render, and the
// summary wrapper returns "none" rather than pretending to an age it cannot
// measure. readCurrency itself never returns "none": give it stamps and it
// gives a verdict -- the arc, the bearings and every other read-back reuse
// it with their own made/now pair.

export type Currency = "fresh" | "aged" | "old";
export type SummaryCurrency = Currency | "none";

/** The stamps a read-back carries: the TURN it was made at, the turn now,
 *  the sha of the code that made it, the sha running. Every field may be
 *  absent; an absent stamp breaks its axis (never a false "fresh"). */
export interface CurrencyStamps {
  made_turn?: number | null;
  now_turn?: number | null;
  made_sha?: string | null;
  live_sha?: string | null;
}

export interface SummaryCurrencyMeta {
  summary?: string | null;
  /** #139 / #190 -- the message_count the summary was made at. */
  summary_turn?: number | null;
  /** The thread's message_count now. */
  message_count?: number | null;
  /** #127 — the COMMIT_SHA of the code that made the summary. Absent on
   *  rows that predate the stamp; never backfilled. */
  summary_commit_sha?: string | null;
  // kept on the type for older readers; NOT read by the verdict (#190)
  summary_ts_ms?: number | null;
  updated_at?: number | null;
}

/** Seconds-or-milliseconds → milliseconds, by magnitude. 1e11 ms is 1973;
 *  1e11 s is the year 5138. Nothing real sits on the wrong side. A stamp
 *  formatter's helper; the verdict never calls it. */
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

/** A turn stamp, or null: a non-negative integer and nothing else. */
export function normTurn(t: number | null | undefined): number | null {
  return typeof t === "number" && Number.isInteger(t) && t >= 0 ? t : null;
}

/**
 * #190 -- the ONE verdict every read-back uses. No clock.
 *   fresh  made_turn === now_turn AND made_sha === live_sha
 *   aged   exactly one of the two holds
 *   old    neither holds -- including "no stamp at all"
 */
export function readCurrency(stamps: CurrencyStamps | null | undefined): Currency {
  // "One broke -> aged; both or NO STAMP -> old" (the brief): a row with no
  // made_turn cannot claim an age at all, so it is old even when the sha
  // matches -- the one unmeasurable case resolves away from fresh AND aged.
  const s = stamps ?? {};
  const made = normTurn(s.made_turn);
  if (made === null) return "old";   // no stamp -> old, whatever the sha says (the brief's letter)
  const now = normTurn(s.now_turn);
  const turnOk = now !== null && made === now;
  const madeSha = normSha(s.made_sha);
  const liveSha = normSha(s.live_sha);
  const shaOk = madeSha !== null && liveSha !== null && madeSha === liveSha;
  if (turnOk && shaOk) return "fresh";
  if (turnOk || shaOk) return "aged";
  return "old";
}

/** The summary card's reading: "none" when there is no summary, otherwise
 *  readCurrency over the summary's stamps and the live sha. */
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

/** #219 (CT-1 2026-09-09) -- ABSENCE NAMES ITS REASON. The caption used to
 *  read "made turn — · now turn 12", which tells a member nothing: an em
 *  dash is the right KIND for a missing reading but the wrong thing to
 *  show someone who wants to know whether their summary is current. A
 *  summary with no turn stamp was made before the stamp existed, so the
 *  caption says that, in one sentence, with no jargon and no id.
 *
 *  With a stamp it is unchanged: "made turn a · now turn b". This touches
 *  the caption ONLY -- readCurrency and summaryCurrency, which pick the
 *  band (#190), are not in this function and are not changed. */
export const UNSTAMPED_CAPTION = "not stamped — summarized before the stamp shipped";

export function turnCaption(stamps: CurrencyStamps | null | undefined): string {
  const s = stamps ?? {};
  const made = normTurn(s.made_turn);
  if (made === null) return UNSTAMPED_CAPTION;
  const now = normTurn(s.now_turn);
  return `made turn ${made} · now turn ${now === null ? "—" : now}`;
}
