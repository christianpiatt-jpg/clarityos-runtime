// services/vault.ts — read-only summary helpers around the existing vault store.
// The cockpit's Vault Status Indicator only needs counts; the full Vault route
// (web/src/routes/Vault.tsx) handles CRUD via the existing lib/api.ts.

import { vaultList } from "../lib/api";

export interface VaultSummary {
  total_items: number;
  total_bytes: number;
  by_kind: Record<string, number>;
}

export async function fetchVaultSummary(): Promise<VaultSummary> {
  const r = await vaultList(500);
  // vaultList returns { ok, items: [...] } — derive a count summary locally.
  // Do NOT pull item bodies; we already have them but only inspect metadata.
  // TODO(envelope-integration): once /vault/summary lands server-side, swap
  // this for a single-roundtrip metadata fetch instead of a full list.
  const items = (r as any)?.items ?? [];
  const by_kind: Record<string, number> = {};
  let total_bytes = 0;
  for (const it of items) {
    const kind = String(it?.kind ?? "vault");
    by_kind[kind] = (by_kind[kind] ?? 0) + 1;
    total_bytes += Number(it?.size_bytes ?? 0);
  }
  return { total_items: items.length, total_bytes, by_kind };
}
