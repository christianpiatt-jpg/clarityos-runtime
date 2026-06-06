"""ClarityOS Engine v1 — Phase-1 deterministic analytics.

Pure-Python implementations of the hydraulic-physics primitives,
synthetic-origin regression, forward projection, and diagnostics that
``POST /engine/v1/run`` (Card "Engine V1 Contract — Phase 1") returns.

Sources:
    * "Double Historical Predictive Regression" (HydraulicState, Primitive,
      RegressionResult, ProjectionResult)
    * "Godhard Curve Integration" (critical-zone metrics → OverlayResult)
    * "Phenomenological Metadata Collection" (Diagnostics shape)

The wire contract is owned by the Pydantic models in ``app.py``; this
module deals in plain ``dict`` payloads so the route can build, transform,
and re-validate via ``EngineResponseV1.model_validate`` cheaply. No I/O,
no globals beyond constants, no randomness.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Hydraulic constants — from "Double Historical Predictive Regression"
# ---------------------------------------------------------------------------
PRESSURE_DECAY_PER_DAY: float = 0.05
FLOW_DECAY_PER_DAY:     float = 0.03
RESISTANCE_GROWTH_PER_DAY: float = 0.02

REYNOLDS_LAMINAR_MAX:    float = 2000.0
REYNOLDS_TURBULENT_MIN:  float = 4000.0
REYNOLDS_SCALE:          float = 400.0   # matches the source doc's formula

# Godhard critical-zone constants (the doc's bistable-region window)
GODHARD_CENTER:      float = 5.0
GODHARD_HALF_WIDTH:  float = 1.5
GODHARD_LOWER_BOUND: float = GODHARD_CENTER - GODHARD_HALF_WIDTH
GODHARD_UPPER_BOUND: float = GODHARD_CENTER + GODHARD_HALF_WIDTH

# Regime → stability score (laminar / transitional / turbulent)
_REGIME_STABILITY: dict[str, float] = {
    "laminar":      0.9,
    "transitional": 0.5,
    "turbulent":    0.2,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reynolds(pressure: float, flow: float, resistance: float) -> float:
    """Re = (flow · pressure · scale) / max(resistance, 0.1).

    Zero resistance saturates to 10_000 (treated as fully turbulent).
    """
    if resistance <= 0:
        return 10_000.0
    return (flow * pressure * REYNOLDS_SCALE) / max(resistance, 0.1)


def _flow_regime(reynolds: float) -> str:
    if reynolds < REYNOLDS_LAMINAR_MAX:
        return "laminar"
    if reynolds < REYNOLDS_TURBULENT_MIN:
        return "transitional"
    return "turbulent"


def _new_primitive_id() -> str:
    return f"prim_{uuid.uuid4().hex[:12]}"


def _new_observation_id() -> str:
    return f"obs_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# build_primitive — request-input spec → wire-shape EnginePrimitive
# ---------------------------------------------------------------------------
def build_primitive(spec: dict) -> dict:
    """Translate one ``EnginePrimitiveInput`` dict into a full ``EnginePrimitive``.

    Missing optional fields fall back to documented defaults. The same
    timestamp is stamped on metadata and hydraulic_state so a primitive
    is internally consistent. ancestors / depends_on / influences plus
    origin_state / historical_states are present-but-empty in Phase-1
    (the wire shape is locked early; values land when the archive does).
    """
    pid = spec.get("primitive_id") or _new_primitive_id()
    ts = _now_iso()
    return {
        "metadata": {
            "primitive_id":   pid,
            "primitive_type": spec.get("primitive_type") or "signal",
            "timestamp":      ts,
            "version":        "1.0.0",
            "domain":         spec.get("domain") or "general",
            "source":         spec.get("source") or "",
            "parent_id":      None,
            "ancestors":      [],
            "depends_on":     [],
            "influences":     [],
            "confidence":     1.0,
            "completeness":   1.0,
            "reliability":    1.0,
        },
        "content": dict(spec.get("content") or {}),
        "hydraulic_state": {
            "pressure":   float(spec["pressure"]),
            "gradient":   float(spec.get("gradient") or 0.0),
            "flow":       float(spec["flow"]),
            "resistance": float(spec["resistance"]),
            "timestamp":  ts,
        },
        "origin_state":      None,
        "historical_states": [],
    }


# ---------------------------------------------------------------------------
# compute_overlay — Godhard-curve overlay derived from a Primitive
# ---------------------------------------------------------------------------
def compute_overlay(primitive: dict) -> dict:
    h = primitive["hydraulic_state"]
    re = _reynolds(h["pressure"], h["flow"], h["resistance"])
    regime = _flow_regime(re)

    # Curve position ≈ normalised pressure (Phase-1 simplification).
    position = min(10.0, max(0.0, float(h["pressure"])))
    distance_to_fold = abs(position - GODHARD_CENTER)
    in_critical_zone = GODHARD_LOWER_BOUND < position < GODHARD_UPPER_BOUND
    # Resilience inversely tracks distance from the critical centre.
    resilience = max(0.0, 10.0 - 2.0 * distance_to_fold)
    # Card 20 cherry-pick (Godhard fields):
    # - on_upper_branch: position above the curve centre (Phase-1 heuristic
    #   — Phase-2 will track the true hysteresis branch).
    # - sensitivity: local S-curve slope; peaks at the critical centre,
    #   baseline 1.0 outside the bistable window.
    # - hysteresis: the configured loop width (static for Phase-1).
    on_upper_branch = position > GODHARD_CENTER
    sensitivity     = 1.0 + 2.0 * max(0.0, GODHARD_HALF_WIDTH - distance_to_fold)
    hysteresis      = GODHARD_HALF_WIDTH * 2.0

    return {
        "primitive_id":     primitive["metadata"]["primitive_id"],
        "reynolds_number":  round(re, 3),
        "flow_regime":      regime,
        "stability":        _REGIME_STABILITY[regime],
        "in_critical_zone": in_critical_zone,
        "distance_to_fold": round(distance_to_fold, 3),
        "resilience":       round(resilience, 3),
        "curve_position":   round(position, 3),
        "on_upper_branch":  on_upper_branch,
        "sensitivity":      round(sensitivity, 3),
        "hysteresis":       round(hysteresis, 3),
    }


# ---------------------------------------------------------------------------
# regress_to_origin — synthetic-origin regression (Phase-1)
# ---------------------------------------------------------------------------
def regress_to_origin(primitive: dict, assumed_age_days: int = 90) -> dict:
    """Reverse the decay constants to estimate an origin state, then
    interpolate a 21-point path between current and origin.

    Phase-1 has no historical archive, so origin is synthetic by
    construction and reconstruction_error is reported as 0.0 (perfect
    by construction). path_confidence is held at the source-doc's
    "synthetic origin" default of 0.7.
    """
    h = primitive["hydraulic_state"]
    origin_pressure   = max(1.0, h["pressure"]   - PRESSURE_DECAY_PER_DAY    * assumed_age_days)
    origin_flow       = min(10.0, h["flow"]      + FLOW_DECAY_PER_DAY        * assumed_age_days)
    origin_resistance = max(0.5, h["resistance"] - RESISTANCE_GROWTH_PER_DAY * assumed_age_days)

    origin_ts = (datetime.now(timezone.utc) - timedelta(days=assumed_age_days)).isoformat()

    origin = {
        "metadata": {
            **primitive["metadata"],
            "timestamp":  origin_ts,
            "confidence": 0.7,  # synthetic → lower confidence than current
        },
        "content": dict(primitive["content"]),
        "hydraulic_state": {
            "pressure":   round(origin_pressure,   3),
            "gradient":   0.0,
            "flow":       round(origin_flow,       3),
            "resistance": round(origin_resistance, 3),
            "timestamp":  origin_ts,
        },
    }

    steps = 20
    path: list[dict] = []
    for i in range(steps + 1):
        alpha = i / steps  # 0 = current, 1 = origin
        path.append({
            "metadata": dict(primitive["metadata"]),
            "content":  dict(primitive["content"]),
            "hydraulic_state": {
                "pressure":   round(h["pressure"]   * (1 - alpha) + origin_pressure   * alpha, 3),
                "gradient":   0.0,
                "flow":       round(h["flow"]       * (1 - alpha) + origin_flow       * alpha, 3),
                "resistance": round(h["resistance"] * (1 - alpha) + origin_resistance * alpha, 3),
                "timestamp":  h["timestamp"],
            },
        })

    deviation = round(
        abs(h["pressure"]   - origin_pressure)
        + abs(h["flow"]       - origin_flow)
        + abs(h["resistance"] - origin_resistance),
        3,
    )

    return {
        "primitive_id":           primitive["metadata"]["primitive_id"],
        "current_state":          primitive,
        "origin_state":           origin,
        "path":                   path,
        "reconstruction_error":   0.0,
        "path_confidence":        0.7,
        "deviation_from_origin":  deviation,
        "historical_similarity":  0.5,  # no archive in Phase-1
        "attitude_match_score":   0.5,
    }


# ---------------------------------------------------------------------------
# project_forward — deterministic forward projection (Phase-1)
# ---------------------------------------------------------------------------
def project_forward(primitive: dict, days: int = 30) -> dict:
    """Apply the per-day decay constants for ``days`` steps. Records
    every regime transition so the wire response can render them."""
    if days < 0:
        raise ValueError("projection days must be non-negative")

    h = primitive["hydraulic_state"]
    pressures: list[float] = [round(h["pressure"], 4)]
    flows:     list[float] = [round(h["flow"],     4)]

    cur_p, cur_f, cur_r = h["pressure"], h["flow"], h["resistance"]
    initial_regime = _flow_regime(_reynolds(cur_p, cur_f, cur_r))
    regime_changes: list[dict] = [{"day": 0, "regime": initial_regime}]

    for d in range(1, days + 1):
        cur_p = max(0.0, cur_p - PRESSURE_DECAY_PER_DAY)
        cur_f = max(0.0, cur_f - FLOW_DECAY_PER_DAY)
        cur_r = min(10.0, cur_r + RESISTANCE_GROWTH_PER_DAY)
        pressures.append(round(cur_p, 4))
        flows.append(round(cur_f, 4))
        new_regime = _flow_regime(_reynolds(cur_p, cur_f, cur_r))
        if new_regime != regime_changes[-1]["regime"]:
            regime_changes.append({"day": d, "regime": new_regime})

    projected_ts = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    projected = {
        "metadata": {
            **primitive["metadata"],
            "timestamp": projected_ts,
        },
        "content": dict(primitive["content"]),
        "hydraulic_state": {
            "pressure":   round(cur_p, 3),
            "gradient":   round(-PRESSURE_DECAY_PER_DAY, 4),
            "flow":       round(cur_f, 3),
            "resistance": round(cur_r, 3),
            "timestamp":  projected_ts,
        },
    }

    # Confidence decays linearly with projection horizon (90-day max).
    confidence  = max(0.3, 1.0 - (days / 90.0) * 0.2)
    uncertainty = round(0.05 * (1.0 + days / 30.0), 4)

    return {
        "primitive_id":        primitive["metadata"]["primitive_id"],
        "source_state":        primitive,
        "projected_state":     projected,
        "projection_days":     days,
        "confidence":          round(confidence, 3),
        "uncertainty":         uncertainty,
        "pressure_trajectory": pressures,
        "flow_trajectory":     flows,
        "regime_changes":      regime_changes,
    }


# ---------------------------------------------------------------------------
# build_diagnostics — phenomenological-metadata shape (Phase-1 subset)
# ---------------------------------------------------------------------------
def build_diagnostics(
    primitives: list[dict],
    overlays:   list[dict],
    notes:      Optional[str] = None,
) -> dict:
    early_warnings: dict[str, float] = {}
    if overlays:
        critical = [o for o in overlays if o["in_critical_zone"]]
        if critical:
            early_warnings["critical_zone_count"] = float(len(critical))
            early_warnings["min_resilience"] = min(o["resilience"] for o in overlays)
        early_warnings["mean_reynolds"] = round(
            sum(o["reynolds_number"] for o in overlays) / len(overlays), 3,
        )

    return {
        "observation_id":    _new_observation_id(),
        "observer_notes":    notes or "engine_v1 Phase-1 deterministic run",
        "confidence_level":  0.7,
        "validation_status": "unvalidated",
        "early_warnings":    early_warnings,
        "errors":            [],
        # Card 20 cherry-pick: empty in Phase-1; populated when an
        # intervention recipes catalogue lands in a later card.
        "interventions":     [],
    }


# ---------------------------------------------------------------------------
# Top-level run — what the route handler calls
# ---------------------------------------------------------------------------
def run(
    primitive_specs: list[dict],
    *,
    projection_days: int = 30,
) -> dict:
    """Build primitives, overlays, regression (on the first primitive),
    projection (same), and diagnostics. Returns a dict shaped to
    ``EngineResponseV1``; the route handler hands it to
    ``EngineResponseV1.model_validate`` to enforce the contract."""
    primitives = [build_primitive(s) for s in primitive_specs]
    overlays   = [compute_overlay(p) for p in primitives]

    if primitives:
        regression: Optional[dict] = regress_to_origin(primitives[0])
        projection: Optional[dict] = project_forward(primitives[0], days=projection_days)
    else:
        regression = None
        projection = None

    diagnostics = build_diagnostics(primitives, overlays)

    return {
        "ok":             True,
        "primitives":     primitives,
        "overlays":       overlays,
        "regression":     regression,
        "projection":     projection,
        "diagnostics":    diagnostics,
        # Phase-2 / Phase-3 reserved fields are omitted (None on the
        # Pydantic side); clients should treat them as optional.
    }
