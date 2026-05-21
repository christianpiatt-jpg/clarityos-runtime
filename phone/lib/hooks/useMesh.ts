// hooks/useMesh.ts (phone)

import { useCallback, useEffect, useState } from "react";
import {
  buildDeviceMetadataFromSnapshot,
  fetchMeshState,
  pushDeviceMetadata,
  type MeshState,
} from "../services/mesh";
import type { ContinuitySnapshot } from "../services/continuity";

export interface UseMeshOptions {
  deviceId: string;
  pushOnSnapshot?: ContinuitySnapshot | null;
}

export interface UseMeshResult {
  mesh: MeshState | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  push: (metadata: Record<string, unknown>) => Promise<void>;
}

export function useMesh({ deviceId, pushOnSnapshot }: UseMeshOptions): UseMeshResult {
  const [mesh, setMesh] = useState<MeshState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const m = await fetchMeshState();
      setMesh(m);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const push = useCallback(async (metadata: Record<string, unknown>) => {
    try {
      await pushDeviceMetadata(deviceId, metadata);
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  }, [deviceId]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!pushOnSnapshot) return;
    void push(buildDeviceMetadataFromSnapshot(pushOnSnapshot));
  }, [pushOnSnapshot, push]);

  return { mesh, loading, error, refresh, push };
}
