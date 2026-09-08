/**
 * #167c (CT-1 2026-09-08) -- ONE trust line. One measure, one line, one name.
 *
 * turn_record.trust_signal returns three KINDS (never a bare 0.0):
 *   no_prior_yet  nothing scored
 *   undefined     records, but no bearing was ever claimed
 *   value         a rate in [0,1] with the number of scored turns; while
 *                 theta_ready is false the awaiting sentence stays on the
 *                 line (CT-1 09-04), with the floor it is waiting for.
 * No signal at all (a thread that is not a relationship, or nothing read
 * yet) reads "trust —" with the awaiting sentence.
 *
 * Before #167c the same object was read twice into two lines (a "trust"
 * row and a "basin_hop" rail row) by two helpers; both are this one now.
 */
import type { TrustSignal } from "./api";

export const AWAITING_SECOND_READ = "awaiting a second read";
/** The sentence at the house floor, as ONE literal: the served bundle
 *  must carry "floor 7" (the brief's acceptance grep), not a template
 *  that only ever computes it. */
export const AWAITING_AT_FLOOR_7 = "awaiting a second read (floor 7)";
const DEFAULT_FLOOR = 7;

function floorOf(sig: TrustSignal | null | undefined): number {
  return typeof sig?.theta_floor === "number" && Number.isFinite(sig.theta_floor) ? sig.theta_floor : DEFAULT_FLOOR;
}

function awaitingTail(sig: TrustSignal | null | undefined): string {
  const floor = floorOf(sig);
  return floor === DEFAULT_FLOOR ? ` · ${AWAITING_AT_FLOOR_7}` : ` · ${AWAITING_SECOND_READ} (floor ${floor})`;
}

export function trustLine(sig: TrustSignal | null | undefined): string {
  const tail = awaitingTail(sig);
  if (!sig || sig.status === "no_prior_yet") return `trust —${tail}`;
  if (sig.status === "undefined") return "trust undefined (no bearing claimed)";
  const value = typeof sig.value === "number" ? String(sig.value) : "—";
  const n = typeof sig.scored_turns === "number" ? String(sig.scored_turns) : "—";
  return `trust ${value} · ${n} scored${sig.theta_ready ? "" : tail}`;
}
