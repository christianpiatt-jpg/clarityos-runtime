// web/src/lib/emotionalPhysics.ts
//
// Typed client for POST /me/emotional_physics/analyze (v52).
//
// Web mirror of desktop/src/lib/emotionalPhysics.ts. Only the
// ``getApiBase`` import path differs (web stores it in ./config,
// desktop inlines it in ./api).
//
// Layer names mirror the canonical set on the backend exactly
// (see intelligence_kernel.py::_EMOTIONAL_PHYSICS_KEYS). Kept as its
// own module (not folded into lib/api.ts) because the
// EmotionalPhysicsView v1 component imports the typed envelope and
// the ``analyzeEmotionalPhysics`` runner with a stricter shape than
// the looser legacy helper.

import { ApiError, getSession } from "./api";
import { getApiBase } from "./config";

// Four top-level layer keys. Canonical naming.
//
//   field_curvature       — internal state pattern (NOT feelings or diagnoses)
//   edge_pressure         — externally legible signal pattern (how it lands on others)
//   relational_primitives — underlying relational structure (cross-cultural units)
//   external_expression   — stabilised communication and action guidance
export interface EmotionalPhysicsLayers {
  field_curvature:       Record<string, unknown>;
  edge_pressure:         Record<string, unknown>;
  relational_primitives: Record<string, unknown>;
  external_expression:   Record<string, unknown>;
}

export interface EmotionalPhysicsResponse extends EmotionalPhysicsLayers {
  _meta?: {
    model_id?:    string | null;
    ts_ms?:       number | null;
    parse_error?: string | null;
    [k: string]:  unknown;
  };
  [k: string]: unknown;
}

export interface EmotionalPhysicsRequest {
  text: string;
}

/**
 * Call /me/emotional_physics/analyze. Returns the four-layer object on
 * 200. Throws ApiError on non-200 or empty input.
 */
export async function analyzeEmotionalPhysics(
  req: EmotionalPhysicsRequest,
): Promise<EmotionalPhysicsResponse> {
  const session = getSession();
  if (!session) {
    throw new ApiError("no_session", "not authenticated", 401);
  }
  const text = req.text;
  if (typeof text !== "string" || text.trim().length === 0) {
    throw new ApiError("bad_input", "text must be non-empty", 400);
  }

  const url = `${getApiBase()}/me/emotional_physics/analyze`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": session,
      },
      body: JSON.stringify({ text }),
    });
  } catch (e) {
    throw new ApiError(
      "network",
      e instanceof Error ? e.message : "network failure",
      0,
    );
  }

  let body: unknown = null;
  try { body = await res.json(); } catch { /* leave null */ }

  if (!res.ok) {
    const code =
      isObj(body) && isObj(body.detail) && typeof body.detail.code === "string"
        ? body.detail.code
        : "emotional_physics_failed";
    const message =
      isObj(body) && isObj(body.detail) && typeof body.detail.message === "string"
        ? body.detail.message
        : res.statusText;
    throw new ApiError(code, message, res.status, body);
  }

  if (!isObj(body)) {
    throw new ApiError(
      "shape_mismatch",
      "response is not an object",
      res.status,
      body,
    );
  }
  return body as EmotionalPhysicsResponse;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}
