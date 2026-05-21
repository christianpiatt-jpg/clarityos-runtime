// services/engines.ts — engine catalog (read-only).

import { getApiBase } from "../lib/config";

export type EngineId = "markov" | "galileo" | "library" | "tizzy";

export interface EngineDescriptor {
  id: EngineId;
  label: string;
  route: string;
  description: string;
}

export async function fetchEngines(): Promise<EngineDescriptor[]> {
  const session = localStorage.getItem("clarityos_session");
  if (!session) throw new Error("missing_session");
  const r = await fetch(`${getApiBase()}/engines`, {
    headers: { "X-Session-ID": session },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `engines HTTP ${r.status}`);
  }
  return (data?.engines ?? []) as EngineDescriptor[];
}
