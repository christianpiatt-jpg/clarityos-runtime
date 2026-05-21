// services/dewey.ts — Dewey metadata layer (READ-ONLY, IDs + counts only).
// Never returns origin_vector or membership object_vector.

import { getApiBase } from "../lib/config";

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
  const session = localStorage.getItem("clarityos_session");
  if (!session) throw new Error("missing_session");
  const r = await fetch(`${getApiBase()}/metadata/dewey`, {
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
