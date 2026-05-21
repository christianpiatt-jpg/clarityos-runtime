// services/vault.ts (phone) — minimal vault summary helper.
// The phone surface mostly relies on the existing vault.tsx screen for full
// CRUD; this helper provides only counts for the cockpit panel.

import { getApiBase, getSession } from "../api";

export interface VaultSummary {
  total_items: number;
}

export async function fetchVaultSummary(): Promise<VaultSummary> {
  const session = getSession();
  if (!session) throw new Error("missing_session");
  const base = await getApiBase();
  // /vault/list returns the same envelope as web; we only need the count.
  // TODO(envelope-integration): swap for /vault/summary when that endpoint
  // is added server-side (no full-payload roundtrip needed).
  const r = await fetch(`${base}/vault/list?limit=500`, {
    headers: { "X-Session-ID": session },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `vault HTTP ${r.status}`);
  }
  const items = (data?.items ?? []) as unknown[];
  return { total_items: items.length };
}
