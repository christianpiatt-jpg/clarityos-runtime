/**
 * Pocket — role helpers (v0.3.12 / Card 17).
 *
 * As of Card 16, the engine's ``/me`` response is authoritative:
 *   * ``me.operator``    — true when the request carries a valid
 *                          Operator token OR the user is in cohort
 *                          ``founder_exception``
 *   * ``me.vault_ready`` — true when the v46 memory vault is
 *                          configured and the per-user key derivation
 *                          succeeds
 *
 * Pocket reads those fields DIRECTLY. The v0.3.10 cohort-and-tier
 * inference (``isFoundingMember`` from cohort==founder, etc.) is
 * removed by Card 17: the backend is the single source of truth.
 *
 * If the backend logic for ``operator`` changes (e.g. a future card
 * extends the rule to cover Founding Members), Pocket inherits the
 * change with zero edits here.
 */
import type { MeResponse } from "../api/client";

export function isOperator(me: MeResponse | null | undefined): boolean {
  return me?.operator === true;
}

export function isVaultReady(me: MeResponse | null | undefined): boolean {
  // Distinct from "missing field" — if vault_ready is absent (older
  // backend), treat as ready so Pocket doesn't show a false alarm.
  return me?.vault_ready !== false;
}

/** Display label for the header / Me page badge. */
export function roleLabel(me: MeResponse | null | undefined): string {
  if (!me) return "guest";
  if (isOperator(me)) return "operator";
  return me.tier ?? "user";
}
