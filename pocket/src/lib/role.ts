/**
 * Pocket — role inference helpers (v0.3.10).
 *
 * Card 13 defines the target contract: the backend's ``/me`` should
 * return ``role: "founding_member" | "operator" | "free"`` and
 * Pocket should branch on that. Until the backend lands that field
 * (one-line addition to ``app.py``'s /me handler), Pocket INFERS
 * the role from the fields ``/me`` already returns today:
 * ``cohort`` and ``tier``.
 *
 * Inference rules:
 *
 *   * ``cohort == "founder"``               -> founding_member  (operator-tier founder)
 *   * ``cohort == "founder_exception"``     -> founding_member  (founder exception flag)
 *   * ``tier   == "founding"``              -> founding_member  (Founding 500 cohort)
 *   * otherwise                              -> free
 *
 * When the backend grows a real ``role`` field, this module flips
 * to read it directly:
 *
 *   export function isFoundingMember(me: MeResponse | null): boolean {
 *     return me?.role === "founding_member" || me?.role === "operator";
 *   }
 *
 * Until then, the inference here is the contract Pocket uses.
 *
 * Why not just push the change to the backend now: Card 14 was
 * explicit about "no backend changes". This module satisfies the
 * card's intent (recognise Founding Members + unlock surface) on
 * the Pocket side alone.
 */
import type { MeResponse } from "../api/client";

/** Cohort values the backend uses for founder-adjacent accounts. */
const FOUNDER_LIKE_COHORTS = new Set<string>([
  "founder",
  "founder_exception",
]);

/** Tier values the backend uses to identify Founding Members. */
const FOUNDING_TIERS = new Set<string>(["founding"]);

/**
 * True when the ``/me`` response identifies this account as a
 * Founding Member. Operators (cohort "founder") are treated as
 * Founding Members for surface-unlock purposes — they get the
 * same access; the operator tooling is a separate concept.
 */
export function isFoundingMember(me: MeResponse | null | undefined): boolean {
  if (!me) return false;
  if (me.cohort && FOUNDER_LIKE_COHORTS.has(me.cohort)) return true;
  if (me.tier && FOUNDING_TIERS.has(me.tier)) return true;
  return false;
}

/**
 * True when the ``/me`` response identifies this account as an
 * operator (cohort "founder" or "founder_exception"). Used for
 * UI affordances that should only appear to operators (e.g. a
 * "founder console" link in the future).
 */
export function isOperator(me: MeResponse | null | undefined): boolean {
  if (!me) return false;
  return me.cohort != null && FOUNDER_LIKE_COHORTS.has(me.cohort);
}

/** Display label for the inferred role. Useful for the badge on /me. */
export function roleLabel(me: MeResponse | null | undefined): string {
  if (!me) return "guest";
  if (isOperator(me)) return "operator";
  if (isFoundingMember(me)) return "founding member";
  return me.tier ?? "free";
}
