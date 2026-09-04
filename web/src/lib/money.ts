/**
 * #142 -- dollars on the surface. The ledger is MICRO-DOLLARS; the member
 * sees dollars at $0.01. CT-1 RULED 09-03/09-04: display floors to the
 * cent (sub-cent -> "$0.00"); the deduction math stays in micro and is
 * never touched here. The backend's usage_billing.micro_to_dollars is the
 * twin; this is the client-side copy for history deltas and optimistic
 * balances.
 */
export const MICRO_PER_DOLLAR = 1_000_000;
const MICRO_PER_CENT = 10_000;

/** "$0.66" for 661054; "$0.00" for 900; "-$1.00" for -1_000_000. */
export function microToDollars(micro: number | null | undefined): string {
  if (typeof micro !== "number" || !Number.isFinite(micro)) return "\u2014";
  const cents = Math.floor(Math.abs(micro) / MICRO_PER_CENT);
  const sign = micro < 0 && cents > 0 ? "-" : "";   // no sign on nothing
  return `${sign}$${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;
}

/** A signed delta: "+$15.00", "-$1.00"; a sub-cent delta is "$0.00" with no
 *  sign, because a sign on nothing asserts a direction the cent cannot show. */
export function fmtDelta(micro: number | null | undefined): string {
  if (typeof micro !== "number" || !Number.isFinite(micro)) return "\u2014";
  const cents = Math.floor(Math.abs(micro) / MICRO_PER_CENT);
  if (cents === 0) return "$0.00";
  return (micro > 0 ? "+" : "") + microToDollars(micro);
}

/** The console types dollars at $0.01; the wire carries micro. Returns
 *  null for anything that is not a finite amount on the cent grid. */
export function dollarsToMicro(text: string): number | null {
  const t = (text ?? "").trim();
  if (!/^-?\d+(\.\d{1,2})?$/.test(t)) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100) * MICRO_PER_CENT;
}
