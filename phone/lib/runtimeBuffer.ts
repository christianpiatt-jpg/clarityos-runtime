// In-memory hand-off for the ClarityObject between /chat and /copy.
//
// URL params can carry the distilled text (small string), but the full
// ClarityObject — sentences, contradictions, pressure signature, etc. —
// can run hundreds of KB on long inputs. This module keeps it in JS
// memory for the brief window between submit and the Copy screen mount.
//
// Lifecycle:
//   chat.tsx submit success → setPendingClarity(c) → router.push('/copy')
//   copy.tsx mount          → takePendingClarity()  // reads + clears
//
// If the user navigates to /copy without a fresh submit (deep link,
// back-forward), takePendingClarity() returns null and the page falls
// back to the params-only path.

import type { ClarityObject } from "./langbridg";

let _pending: ClarityObject | null = null;

export function setPendingClarity(c: ClarityObject | null): void {
  _pending = c;
}

export function takePendingClarity(): ClarityObject | null {
  const c = _pending;
  _pending = null;
  return c;
}

export function peekPendingClarity(): ClarityObject | null {
  return _pending;
}
