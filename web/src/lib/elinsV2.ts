// web/src/lib/elinsV2.ts
//
// Typed client for POST /elins/v2/run (v53 Path-C adapter). Types
// mirror the envelope produced by ELINS/elins_v2_view.py::build_v2_envelope.
//
// Web mirror of desktop/src/lib/elinsV2.ts. Only the getApiBase import
// path differs (web stores it in ./config, desktop inlines it in ./api).
//
// No new backend contracts. No mutation. Pure HTTP + typed response.

import { ApiError, getSession } from "./api";
import { getApiBase } from "./config";

// -----------------------------------------------------------------
// Types — mirror ELINS/elins_v2_view.py envelope exactly.
// -----------------------------------------------------------------

export type CollapseState = "none" | "soft" | "hard";
export type Attractor = "S1" | "S2" | "S3" | "S4";
export type GeographyTier = "T1" | "T2" | "T3" | "T4";

export type PKey =
  | "P0" | "P1" | "P2" | "P3" | "P4" | "P5" | "P6" | "P7" | "P8";

export type PrimitiveKey =
  | "pressure" | "tension" | "trust" | "drift" | "contradiction" | "alignment";

export interface ElinsV2Input {
  raw_text: string;
  source_type?: string | null;
  language?: string | null;
  geography_hint?: string | null;
  time_context?: string | null;
  operator_tags?: string[] | null;
}

export interface ElinsV2RunRequest {
  elins_version?: string | null;
  region?: string | null;
  input: ElinsV2Input;
}

export interface ElinsV2EtfAgg {
  n_365: number;
  n_3650: number;
  n_18250: number;
}

export interface ElinsV2L5Pressure {
  primitive: "pressure";
  intensity: number;
  edge_count: number;
}
export interface ElinsV2L6Drift {
  primitive: "drift";
  intensity: number;
  edge_count: number;
}
export interface ElinsV2L9Alignment {
  primitive: "alignment";
  intensity: number;
  edge_count: number;
}

export interface ElinsV2Pipeline {
  L1_ingest:    Record<string, unknown>;
  L2_normalize: { normalized: boolean; note: string };
  L3_domain:    Record<string, unknown>;
  L4_narrative: Record<string, unknown>;
  L5_pressure:  ElinsV2L5Pressure;
  L6_drift:     ElinsV2L6Drift;
  L7_basin:     { region: string | null; available: boolean };
  L8_temporal: {
    forecast_5day:   Record<string, unknown>;
    forecast_engine: Record<string, unknown>;
    etf_table:       Partial<Record<PrimitiveKey, Record<string, number>>>;
    etf_agg:         ElinsV2EtfAgg;
  };
  L9_alignment:  ElinsV2L9Alignment;
  L10_signature: Record<string, unknown>;
}

export interface ElinsV2Outputs {
  collapse_state:     CollapseState;
  attractor:          Attractor;
  state_distribution: Record<Attractor, number>;
  P0_P8:              Record<PKey, number>;
  geography_tier:     GeographyTier | null;
  timeline: {
    short_term_days: number;
    mid_term_days:   number;
    long_term_days:  number;
  };
  multiplier: number;     // [1.0, 2.0]
}

export interface ElinsV2Meta {
  engine:    string;
  view_kind: string;
  warnings:  string[];
  notes:     string[];
}

export interface ElinsV2Envelope {
  elins_version: string;
  region:        string | null;
  input:         Record<string, unknown>;
  pipeline:      ElinsV2Pipeline;
  outputs:       ElinsV2Outputs;
  meta:          ElinsV2Meta;
}

// -----------------------------------------------------------------
// Client
// -----------------------------------------------------------------

/**
 * Call /elins/v2/run. Returns the envelope on 200.
 * Throws ApiError with the backend's error envelope on non-200.
 *
 * No retries. No mutation of the input object.
 */
export async function runElinsV2(req: ElinsV2RunRequest): Promise<ElinsV2Envelope> {
  const session = getSession();
  if (!session) {
    throw new ApiError("no_session", "not authenticated", 401);
  }

  const text = req.input?.raw_text;
  if (typeof text !== "string" || text.trim().length === 0) {
    throw new ApiError("bad_input", "input.raw_text must be non-empty", 400);
  }

  const url = `${getApiBase()}/elins/v2/run`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": session,
      },
      body: JSON.stringify({
        elins_version: req.elins_version ?? null,
        region:        req.region ?? null,
        input: {
          raw_text:       req.input.raw_text,
          source_type:    req.input.source_type ?? null,
          language:       req.input.language ?? null,
          geography_hint: req.input.geography_hint ?? null,
          time_context:   req.input.time_context ?? null,
          operator_tags:  req.input.operator_tags ?? null,
        },
      }),
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
        : "elins_v2_run_failed";
    const message =
      isObj(body) && isObj(body.detail) && typeof body.detail.message === "string"
        ? body.detail.message
        : res.statusText;
    throw new ApiError(code, message, res.status, body);
  }

  if (!isElinsV2Envelope(body)) {
    throw new ApiError(
      "shape_mismatch",
      "response is not a v2 envelope",
      res.status,
      body,
    );
  }
  return body;
}

// -----------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}

function isElinsV2Envelope(v: unknown): v is ElinsV2Envelope {
  if (!isObj(v)) return false;
  if (typeof v.elins_version !== "string") return false;
  if (!isObj(v.pipeline) || !isObj(v.outputs) || !isObj(v.meta)) return false;
  const o = v.outputs as Record<string, unknown>;
  if (typeof o.collapse_state !== "string") return false;
  if (typeof o.attractor !== "string") return false;
  if (!isObj(o.state_distribution) || !isObj(o.P0_P8)) return false;
  if (typeof o.multiplier !== "number") return false;
  return true;
}
