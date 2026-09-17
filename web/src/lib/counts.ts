/**
 * #305 / #307 (CT-1 2026-09-16) -- COUNT WHAT COUNTS. The words a surface
 * uses when a reading has too few points to say more, in ONE place.
 *
 *   n_points      the S-card's n, ON THE WIRE (`_meta.n_points`, #307 E1):
 *                 scored turns of the run's relationship on the personal
 *                 surface, 1 anywhere else. The card reads only that.
 *   a prior read  n >= 2. Below it S1/S2 are retired (B-2: trust and
 *                 alignment are two-frame comparisons), a forecast has no
 *                 trend, and the weather sentence drops its verb.
 *   edges         pipeline.L4_narrative.edge_count. While it is 0 the
 *                 envelopes, the P-grid and the multiplier are derived from
 *                 the stress intensities alone, and say so.
 *   hits          a stress intensity is raw / 4.0 with one 0.3-weight hit at
 *                 0.075 (ELINS/standard_elins._layer_1_primitives). The cap
 *                 of 5 in _count_matches is per TOKEN OCCURRENCE, so k is the
 *                 order's formula, not a true count, and can exceed 5 (a 1.0
 *                 intensity reads 13). Rendered on a single primitive's
 *                 intensity only -- never on the signature's four-primitive
 *                 sum. The unit is CT-1's to re-rule.
 */

export const NEEDS_PRIOR_READ =
  "S1/S2 need a prior read — trust/alignment retired at single read (B-2)";
export const ONE_POINT_NO_TREND = "one point — no trend";
export const DERIVED_FROM_STRESS_ONLY = "derived from stress only";
export const HIT_UNIT = 0.075;
export const HIT_CAP = 5;

/** "k of 5 hits", k = round(intensity / 0.075); a non-number is a dash. */
export function stressHits(intensity: number | null | undefined): string {
  if (typeof intensity !== "number" || !Number.isFinite(intensity)) return "—";
  return `${Math.round(intensity / HIT_UNIT)} of ${HIT_CAP} hits`;
}

/** "1 read — needs 2" (F): in place of STABLE / 100 / a percentage at n < 2. */
export function readsNeeded(n: number): string {
  return `${n} read${n === 1 ? "" : "s"} — needs 2`;
}

/** "sealed at turn N" from `_meta.window_last_message`; a missing number is a dash. */
export function sealedAtTurn(n: unknown): string {
  return `sealed at turn ${typeof n === "number" && Number.isFinite(n) ? n : "—"}`;
}

function metaOf(env: unknown): Record<string, unknown> {
  const m = (env as { _meta?: unknown } | null | undefined)?._meta;
  return m !== null && typeof m === "object" ? (m as Record<string, unknown>) : {};
}

/** `_meta.n_points` as sent, or null when the wire carries none. */
export function nPointsOf(env: unknown): number | null {
  const n = metaOf(env).n_points;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

/**
 * #330 -- `_meta.prior_s_state`: the S-state the PREVIOUS turn sealed, or
 * null when there is no prior seal (the first turn of a relationship, a run
 * that names no thread, or a backend from before this leg). Null is the
 * ABSENT case and the card must say so in words -- never render it as a 0
 * and never as a blank.
 */
export function priorSStateOf(env: unknown): string | null {
  const s = metaOf(env).prior_s_state;
  return typeof s === "string" && s.trim() ? s : null;
}

/**
 * #330 -- `_meta.s_state_match`: did THIS run reach the state the previous
 * turn sealed. Null when either side is absent -- "this reading was not
 * taken", which is nothing to be right or wrong about.
 *
 * ★ AND THE LEDGER CURRENTLY DISAGREES WITH THAT, which is a ruling owed to
 * CT-1 and not a rendering bug. When a prior turn sealed a state and this
 * turn took no reading, score_record scores the record `missed` (a claimed
 * key against an observation that never answered), while this row says
 * `undefined`. The row is the honest one; the scorer's third case is the
 * one-branch ruling named in the #330 RETURN. Do not "fix" the row to match
 * the ledger -- that would print a miss nobody earned.
 */
export function sStateMatchOf(env: unknown): boolean | null {
  const m = metaOf(env).s_state_match;
  return typeof m === "boolean" ? m : null;
}

/**
 * #330 -- `_meta.observed_prior`: was there a prior seal at all. Lets the row
 * separate "no prior turn" from "a prior turn that named no state" -- the
 * second is the COMMON case, because the seal is gated by the surface's own
 * tie rule and a level field names nothing.
 */
export function observedPriorOf(env: unknown): boolean {
  return metaOf(env).observed_prior === true;
}

/** `_meta.ring` as sent ("meaning" | "event"), or null. */
export function ringOf(env: unknown): string | null {
  const r = metaOf(env).ring;
  return typeof r === "string" && r.trim() ? r : null;
}

/** pipeline.L4_narrative.edge_count as sent, or null when absent. */
export function edgesOf(env: unknown): number | null {
  const pipe = (env as { pipeline?: unknown } | null | undefined)?.pipeline;
  const l4 = pipe !== null && typeof pipe === "object"
    ? (pipe as Record<string, unknown>).L4_narrative : null;
  const n = l4 !== null && typeof l4 === "object" ? (l4 as Record<string, unknown>).edge_count : null;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

/** A prior stored point exists: n_points >= 2. An absent n is NOT a prior. */
export function hasPrior(n: number | null): boolean {
  return n !== null && n >= 2;
}
