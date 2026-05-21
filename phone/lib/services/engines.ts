// services/engines.ts (phone)

import { getApiBase, getSession } from "../api";

export type EngineId = "markov" | "galileo" | "library" | "tizzy";

export interface EngineDescriptor {
  id: EngineId;
  label: string;
  route: string;
  description: string;
}

export async function fetchEngines(): Promise<EngineDescriptor[]> {
  const session = getSession();
  if (!session) throw new Error("missing_session");
  const base = await getApiBase();
  const r = await fetch(`${base}/engines`, {
    headers: { "X-Session-ID": session },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `engines HTTP ${r.status}`);
  }
  return (data?.engines ?? []) as EngineDescriptor[];
}
