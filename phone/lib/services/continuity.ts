// services/continuity.ts (phone)

import { continuitySnapshot, type ContinuitySnapshot } from "../api";

export type { ContinuitySnapshot };

export async function fetchContinuitySnapshot(): Promise<ContinuitySnapshot> {
  const r = await continuitySnapshot();
  return r.snapshot;
}
