// services/mesh.ts (phone) — Dewey-only metadata mesh.

import { meshState, meshSync, type MeshState, type ContinuitySnapshot } from "../api";

export function buildDeviceMetadataFromSnapshot(snapshot: ContinuitySnapshot): Record<string, unknown> {
  return {
    surface: "phone",
    counts: snapshot.counts ?? {},
    last_updated_ts: snapshot.last_updated_ts ?? {},
    coherence_flags: snapshot.coherence_flags ?? {},
    observed_at: Date.now() / 1000,
  };
}

export async function pushDeviceMetadata(
  deviceId: string,
  metadata: Record<string, unknown>,
): Promise<{ metadata: Record<string, unknown>; last_seen_ts: number }> {
  const r = await meshSync(deviceId, metadata);
  return r.device;
}

export async function fetchMeshState(): Promise<MeshState> {
  const r = await meshState();
  return r.state;
}

export type { MeshState };
