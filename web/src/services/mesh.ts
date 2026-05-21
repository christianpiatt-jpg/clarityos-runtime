// services/mesh.ts — Dewey-only metadata mesh.
// Never push user content; the device summary helper builds a strict-metadata
// blob from the runtime envelope (counts + last_updated_ts only).

import { meshState, meshSync, type MeshState } from "../lib/api";
import type { ContinuitySnapshot } from "../lib/api";

/** Build a Dewey-safe metadata payload from a continuity snapshot. */
export function buildDeviceMetadataFromSnapshot(snapshot: ContinuitySnapshot): Record<string, unknown> {
  return {
    surface: "web",
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
