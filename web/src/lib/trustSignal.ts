/**
 * #162 (d) -- the awaiting rail speaks trust_signal's status.
 *
 * turn_record.trust_signal returns three KINDS (never a bare 0.0):
 *   no_prior_yet  nothing scored -> the sentence, unchanged
 *   undefined     records, but no bearing was ever claimed
 *   value         a rate in [0,1]; `direction` only from the second scored
 *                 turn on. CT-1 ruled 09-04: while theta_ready is false the
 *                 sentence stays beside the value.
 * No signal at all (a thread that is not a relationship, or nothing read
 * yet) renders the sentence the rail always showed.
 */
import type { TrustSignal } from "./api";

export const AWAITING_SECOND_READ = "awaiting a second read";

export function basinHopLine(sig: TrustSignal | null | undefined): string {
  if (!sig || sig.status === "no_prior_yet") {
    return `basin_hop -- ${AWAITING_SECOND_READ}`;
  }
  if (sig.status === "undefined") {
    return "basin_hop -- trust undefined (no bearing claimed)";
  }
  const value = typeof sig.value === "number" ? String(sig.value) : "\u2014";
  const dir = sig.direction ? ` \u00b7 ${sig.direction}` : "";
  const tail = sig.theta_ready ? "" : ` \u00b7 ${AWAITING_SECOND_READ}`;
  return `basin_hop -- trust ${value}${dir}${tail}`;
}
