// services/dewey.ts (phone) — Dewey metadata layer.
// Returns IDs + counts only; never returns origin_vector or membership vectors.

import { getApiBase, getSession } from "../api";

export interface DeweyNeighborhoodMeta {
  neighborhood_id: string | null;
  name: string | null;
  curvature: number | null;
  has_origin_vector: boolean;
}

export interface DeweyMetadata {
  user: string;
  neighborhood_count: number;
  neighborhoods: DeweyNeighborhoodMeta[];
}

export async function fetchDeweyMetadata(): Promise<DeweyMetadata> {
  const session = getSession();
  if (!session) throw new Error("missing_session");
  const base = await getApiBase();
  const r = await fetch(`${base}/metadata/dewey`, {
    headers: { "X-Session-ID": session },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `metadata/dewey HTTP ${r.status}`);
  }
  return {
    user: data.user,
    neighborhood_count: data.neighborhood_count,
    neighborhoods: data.neighborhoods,
  };
}
