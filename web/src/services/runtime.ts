// services/runtime.ts — read-only envelope viewer.
// Wraps `/runtime/envelope` and `/markov/envelope/latest`.

import { markovEnvelopeLatest, type MarkovEnvelopeLatest } from "../lib/api";
import { getApiBase } from "../lib/config";

/** Heavy-vector descriptor returned by `/runtime/envelope`. */
export interface VectorDescriptor {
  _vector: true;
  dim: number;
}

/**
 * Full envelope shape returned by `/runtime/envelope`. All large vectors are
 * stripped server-side and replaced with `VectorDescriptor` so the cockpit
 * can render structure without dumping 768 floats.
 */
export interface RuntimeEnvelope {
  user?: string;
  envelope_vector?: VectorDescriptor | null;
  envelope_centroid?: VectorDescriptor | null;
  envelope_drift_events?: number;
  envelope_decay_ts?: number;
  envelope_last_replay_ts?: number;
  last_centroid_update_ts?: number;
  events?: Array<Record<string, unknown>>;
  episodes?: Record<string, Record<string, unknown>>;
  narratives?: Record<string, Record<string, unknown>>;
  story_arcs?: Record<string, Record<string, unknown>>;
  identity?: Record<string, unknown>;
  trajectory?: Record<string, unknown>;
  elins?: Record<string, unknown>;
  universal_physics?: Record<string, unknown>;
  coherence?: Record<string, unknown>;
  external_context?: Record<string, unknown>;
  physics_reasoning_context?: Record<string, unknown>;
  reasoning_cues?: Record<string, unknown>;
  reasoning_weights?: Record<string, unknown>;
  memory_context?: Record<string, unknown>;
  external_knowledge?: Record<string, unknown>;
  cognitive_loop?: Record<string, unknown>;
  reasoning_scaffold?: Record<string, unknown>;
  response_shape?: Record<string, unknown>;
  response_templates?: Record<string, unknown>;
  sentence_operators?: Record<string, unknown>;
  connective_ops?: Record<string, unknown>;
  elins_briefs?: Array<Record<string, unknown>>;
  updated_at?: number;
  [k: string]: unknown;
}

/** Fetch the user's stripped envelope. */
export async function fetchRuntimeEnvelope(): Promise<RuntimeEnvelope> {
  // Inline fetch to avoid coupling to the lib/api.ts request() generic typing.
  const session = localStorage.getItem("clarityos_session");
  if (!session) throw new Error("missing_session");
  const r = await fetch(`${getApiBase()}/runtime/envelope`, {
    headers: { "X-Session-ID": session, "Content-Type": "application/json" },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `runtime/envelope HTTP ${r.status}`);
  }
  return (data?.envelope ?? {}) as RuntimeEnvelope;
}

/** Fetch the slim per-session envelope summary used by the chat path. */
export async function fetchEnvelopeLatest(sessionId: string): Promise<MarkovEnvelopeLatest> {
  return markovEnvelopeLatest(sessionId);
}
