// services/continuity.ts — cross-session metadata snapshot.
// Pure pass-through to /continuity/snapshot; no inference or summarization.

import { continuitySnapshot, type ContinuitySnapshot } from "../lib/api";

export type { ContinuitySnapshot };

export async function fetchContinuitySnapshot(): Promise<ContinuitySnapshot> {
  const r = await continuitySnapshot();
  return r.snapshot;
}
