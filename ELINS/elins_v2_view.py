"""
v53 — ELINS v2 view adapter (Path C).

Pure deterministic projection of the canonical v33-v34 ELINS pipeline
output into the v2.0 response contract. NO new I/O, NO model calls,
NO external services, NO imports from /skills_export/.

  * Reuses ELINS.standard_elins.generate_ELINS for the 10-layer core
  * Reuses ELINS.regional_elins.run_regional_elins (called by the
    kernel) when a region is supplied
  * Adds six analytical heads (ETF / S1-S4 / collapse / P0-P8 /
    geography tier / multiplier) as pure functions over the existing
    layer fields

Spec lock — locked policy thresholds (operator-approved):
  * S4 → hard collapse threshold:        0.40
  * S4 → soft collapse threshold:        0.25
  * field_intensity soft fallback:       0.70
  * tier boundaries T1 / T2 / T3:        1.20 / 0.40 / -0.20
  * S2 = "pressured coherence", S4 = "collapse trajectory"
  * P0-P8 axes = (peaceful / contested / ruptured) × (near / mid / far)

Spec lock — engineering coefficients (deterministic math choices):
  * ETF λ_base = 0.001, α = 0.5, β = 0.1, λ clamp [1e-4, 1e-2]
  * Softmax temperature τ = 1.0
  * Multiplier weights (field / S4 / collapse) = 0.4 / 0.3 / 0.3
  * Pressure-trend significance > 0.05

Public API:
    ELINS_V2_VERSION
    STATES, HORIZONS_DAYS, RESOLUTIONS, TIMESCALES, TIERS

    compute_etf(ep0, edge_count, n_days)        -> float
    compute_state_distribution(intensities)     -> (dict, str)
    compute_collapse_state(state_dist, ep_field_summary,
                           forecast_engine, primitives) -> str
    compute_p0_p8(state_dist, collapse_state,
                  etf_agg_365, etf_agg_3650)    -> dict
    compute_geography_tier(regional_object)     -> Optional[str]
    compute_multiplier(field_intensity, s4_mass,
                       collapse_state)          -> float

    build_v2_envelope(elins_object, *, region=None,
                      regional_object=None,
                      request_input=None)       -> dict
"""
from __future__ import annotations

import math
from typing import Optional

ELINS_V2_VERSION: str = "elins.v2.0"

# Canonical primitive keys (mirrors ELINS.standard_elins.PRIMITIVE_KEYS).
PRIMITIVE_KEYS: tuple = (
    "pressure", "tension", "trust", "drift", "contradiction", "alignment",
)

# Four canonical structural-stability states.
STATES: tuple = ("S1", "S2", "S3", "S4")

# Long-horizon days for ETF aggregation.
HORIZONS_DAYS: tuple = (365, 3650, 18250)

# Resolution + timescale axis labels (P0-P8 grid).
RESOLUTIONS: tuple = ("peaceful", "contested", "ruptured")
TIMESCALES: tuple = ("near", "mid", "far")

# Geography tier ordering (best -> worst).
TIERS: tuple = ("T1", "T2", "T3", "T4")

# §1 — ETF coefficients (locked engineering).
ETF_LAMBDA_BASE: float = 0.001
ETF_ALPHA: float = 0.5
ETF_BETA: float = 0.1
ETF_LAMBDA_MIN: float = 0.0001
ETF_LAMBDA_MAX: float = 0.01

# §3 — Collapse thresholds (locked policy, operator-approved).
S4_HARD_THRESHOLD: float = 0.40
S4_SOFT_THRESHOLD: float = 0.25
FIELD_INTENSITY_SOFT_THRESHOLD: float = 0.70
PRESSURE_TREND_SIGNIFICANCE: float = 0.05

# §3 / §4 / §6 — collapse_state -> numeric weight.
COLLAPSE_WEIGHTS: dict = {"none": 0.0, "soft": 0.5, "hard": 1.0}

# §5 — Geography tier boundaries (locked policy, operator-approved).
TIER_T1_BOUNDARY: float = 1.20
TIER_T2_BOUNDARY: float = 0.40
TIER_T3_BOUNDARY: float = -0.20

# §6 — Multiplier weights (locked engineering).
MULTIPLIER_FIELD_WEIGHT: float = 0.4
MULTIPLIER_S4_WEIGHT: float = 0.3
MULTIPLIER_COLLAPSE_WEIGHT: float = 0.3

# §6 — Multiplier output clamp.
MULTIPLIER_MIN: float = 1.0
MULTIPLIER_MAX: float = 2.0


# ---------------------------------------------------------------------------
# §1 — ETF (Epoch Transfer Function)
# ---------------------------------------------------------------------------
def compute_etf(ep0: float, edge_count: int, n_days: int) -> float:
    """Project a primitive's intensity at day n.

    ``edge_count`` is the degree of the primitive in
    ``causal_chain.edges`` (count of edges incident to the primitive
    as either endpoint). Higher edge_count = more structural
    reinforcement → slower decay.

    Returns the projected intensity in ``[0, ep0]``.
    """
    if not isinstance(n_days, int) or n_days < 0:
        raise ValueError("n_days must be a non-negative int")
    try:
        ep0_f = float(ep0)
    except (TypeError, ValueError) as e:
        raise ValueError("ep0 must be numeric") from e
    if ep0_f <= 0.0:
        return 0.0
    try:
        ec = int(edge_count)
    except (TypeError, ValueError) as e:
        raise ValueError("edge_count must be int-coercible") from e
    if ec < 0:
        ec = 0
    raw_lambda = ETF_LAMBDA_BASE * (1.0 + ETF_ALPHA * ep0_f - ETF_BETA * ec)
    lam = max(ETF_LAMBDA_MIN, min(ETF_LAMBDA_MAX, raw_lambda))
    return round(ep0_f * math.exp(-lam * n_days), 6)


# ---------------------------------------------------------------------------
# §2 — S1-S4 attractor states
# ---------------------------------------------------------------------------
def compute_state_distribution(intensities: dict) -> tuple[dict, str]:
    """Return ``(state_distribution, attractor)``.

    ``state_distribution``: dict keyed S1..S4, each in [0,1], sums to 1.
    ``attractor``: argmax(state_distribution); ties broken by state order S1<S2<S3<S4.
    """
    if not isinstance(intensities, dict):
        raise ValueError("intensities must be a dict")

    def _g(key: str) -> float:
        v = intensities.get(key, 0.0)
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    p  = _g("pressure")
    tr = _g("trust")
    dr = _g("drift")
    cn = _g("contradiction")
    al = _g("alignment")
    # tension is not part of §2 scoring (deliberately).

    score_S1 = (1.0 - p) * al * tr
    score_S2 = p * al * tr
    score_S3 = p * (1.0 - al) * (1.0 - tr)
    score_S4 = p * dr * (1.0 - al) * cn

    raw = {"S1": score_S1, "S2": score_S2, "S3": score_S3, "S4": score_S4}

    # Softmax with τ = 1.0 (locked).
    exps = {k: math.exp(v) for k, v in raw.items()}
    total = sum(exps.values())
    dist = {k: round(exps[k] / total, 4) for k in STATES}

    # Argmax with tie-break by state order.
    best_state = STATES[0]
    best_value = dist[best_state]
    for s in STATES[1:]:
        if dist[s] > best_value:
            best_state = s
            best_value = dist[s]

    return dist, best_state


# ---------------------------------------------------------------------------
# §3 — Collapse threshold classifier
# ---------------------------------------------------------------------------
def compute_collapse_state(
    state_distribution: dict,
    ep_field_summary: dict,
    forecast_engine: dict,
    primitives: dict,
) -> str:
    """Classify collapse risk as ``none`` / ``soft`` / ``hard``."""
    s4 = float((state_distribution or {}).get("S4", 0.0))

    if s4 >= S4_HARD_THRESHOLD:
        return "hard"
    if s4 >= S4_SOFT_THRESHOLD:
        return "soft"

    # Fallback: high field intensity + rising pressure trend at the
    # end of the forecast_engine's pressure envelope (day 5).
    field_intensity = float(
        (ep_field_summary or {}).get("intensity_mean", 0.0)
    )
    pressure_today = float(
        ((primitives or {}).get("intensities") or {}).get("pressure", 0.0)
    )
    pressure_envelope = (
        ((forecast_engine or {}).get("primitive_envelopes") or {})
        .get("pressure") or []
    )
    pressure_end = (
        float(pressure_envelope[-1]) if pressure_envelope else pressure_today
    )
    pressure_trend = pressure_end - pressure_today

    if (field_intensity >= FIELD_INTENSITY_SOFT_THRESHOLD
            and pressure_trend > PRESSURE_TREND_SIGNIFICANCE):
        return "soft"

    return "none"


# ---------------------------------------------------------------------------
# §4 — P0-P8 distribution
# ---------------------------------------------------------------------------
def compute_p0_p8(
    state_distribution: dict,
    collapse_state: str,
    etf_agg_365: float,
    etf_agg_3650: float,
) -> dict:
    """Return the joint distribution over the 3x3 outcome grid.

    Grid mapping (locked):
        P0 = peaceful  × near
        P1 = peaceful  × mid
        P2 = peaceful  × far
        P3 = contested × near
        P4 = contested × mid
        P5 = contested × far
        P6 = ruptured  × near
        P7 = ruptured  × mid
        P8 = ruptured  × far
    """
    sd = state_distribution or {}
    s1 = float(sd.get("S1", 0.0))
    s2 = float(sd.get("S2", 0.0))
    s3 = float(sd.get("S3", 0.0))
    s4 = float(sd.get("S4", 0.0))
    c_w = COLLAPSE_WEIGHTS.get(collapse_state, 0.0)

    # Resolution marginals (per spec §4 formula).
    raw_peaceful  = s1 + 0.5 * s2
    raw_contested = 0.5 * s2 + s3 * (1.0 - c_w)
    raw_ruptured  = s4 + 0.5 * c_w
    R_total = raw_peaceful + raw_contested + raw_ruptured
    if R_total <= 0.0:
        res = {"peaceful": 1.0, "contested": 0.0, "ruptured": 0.0}
    else:
        res = {
            "peaceful":  raw_peaceful / R_total,
            "contested": raw_contested / R_total,
            "ruptured":  raw_ruptured / R_total,
        }

    # Timescale marginals — fraction of intensity dissipating in each band.
    e365  = float(etf_agg_365)
    e3650 = float(etf_agg_3650)
    near_raw = max(0.0, 1.0 - e365)
    mid_raw  = max(0.0, e365 - e3650)
    far_raw  = max(0.0, e3650)
    T_total = near_raw + mid_raw + far_raw
    if T_total <= 0.0:
        t = {"near": 0.0, "mid": 0.0, "far": 1.0}
    else:
        t = {
            "near": near_raw / T_total,
            "mid":  mid_raw / T_total,
            "far":  far_raw / T_total,
        }

    # Joint distribution — resolution outer, timescale inner.
    out: dict[str, float] = {}
    idx = 0
    for r in RESOLUTIONS:
        for ts in TIMESCALES:
            out[f"P{idx}"] = round(res[r] * t[ts], 6)
            idx += 1
    return out


# ---------------------------------------------------------------------------
# §5 — Geography tier
# ---------------------------------------------------------------------------
def compute_geography_tier(regional_object: Optional[dict]) -> Optional[str]:
    """Classify the region into T1/T2/T3/T4 from regional_elins output.

    Returns ``None`` when no regional object is supplied.
    """
    if not regional_object:
        return None
    intensities = (
        (regional_object.get("primitives") or {}).get("intensities") or {}
    )
    field_intensity = float(
        (regional_object.get("ep_field_summary") or {}).get("intensity_mean", 0.0)
    )
    trust     = float(intensities.get("trust", 0.0))
    alignment = float(intensities.get("alignment", 0.0))
    drift     = float(intensities.get("drift", 0.0))

    tier_score = (1.0 - field_intensity) * trust + alignment - drift

    if tier_score >= TIER_T1_BOUNDARY:
        return "T1"
    if tier_score >= TIER_T2_BOUNDARY:
        return "T2"
    if tier_score >= TIER_T3_BOUNDARY:
        return "T3"
    return "T4"


# ---------------------------------------------------------------------------
# §6 — Multiplier
# ---------------------------------------------------------------------------
def compute_multiplier(
    field_intensity: float,
    s4_mass: float,
    collapse_state: str,
) -> float:
    """Scalar amplification factor in ``[1.0, 2.0]``."""
    try:
        fi = float(field_intensity or 0.0)
    except (TypeError, ValueError):
        fi = 0.0
    try:
        s4 = float(s4_mass or 0.0)
    except (TypeError, ValueError):
        s4 = 0.0
    c_w = COLLAPSE_WEIGHTS.get(collapse_state, 0.0)

    multiplier = (
        1.0
        + MULTIPLIER_FIELD_WEIGHT * fi
        + MULTIPLIER_S4_WEIGHT * s4
        + MULTIPLIER_COLLAPSE_WEIGHT * c_w
    )
    multiplier = max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, multiplier))
    return round(multiplier, 3)


# ---------------------------------------------------------------------------
# Orchestrator — build_v2_envelope
# ---------------------------------------------------------------------------
def build_v2_envelope(
    elins_object: dict,
    *,
    region: Optional[str] = None,
    regional_object: Optional[dict] = None,
    request_input: Optional[dict] = None,
) -> dict:
    """Project the v33-v34 generate_ELINS output (and optional regional
    output) into the v2.0 response envelope.

    All six analytical heads are pure functions of fields the existing
    pipeline already emits — no new generative work happens here.

    Raises:
        ValueError: ``elins_object`` is not a dict.
    """
    if not isinstance(elins_object, dict):
        raise ValueError("elins_object must be a dict")

    # Pull the layer outputs we'll need.
    primitives_layer = elins_object.get("primitives") or {}
    intensities = primitives_layer.get("intensities") or {}
    causal_chain = elins_object.get("causal_chain") or {}
    edges = causal_chain.get("edges") or []
    ep_field_summary = elins_object.get("ep_field_summary") or {}
    forecast_engine_layer = elins_object.get("forecast_engine") or {}

    # Degree count per primitive (used as edge_count for ETF).
    edge_count: dict[str, int] = {p: 0 for p in PRIMITIVE_KEYS}
    for e in edges:
        if not isinstance(e, dict):
            continue
        a = e.get("from")
        b = e.get("to")
        if isinstance(a, str) and a in edge_count:
            edge_count[a] += 1
        if isinstance(b, str) and b in edge_count:
            edge_count[b] += 1

    # ETF table: primitive × horizon → projected intensity.
    etf_table: dict[str, dict[int, float]] = {}
    for p in PRIMITIVE_KEYS:
        ep0 = float(intensities.get(p, 0.0))
        etf_table[p] = {}
        for n in HORIZONS_DAYS:
            etf_table[p][n] = compute_etf(ep0, edge_count[p], n)

    # Aggregate "fraction surviving" at each horizon, averaged across
    # primitives that have any presence at all (ep0 > 0). Used by §4.
    def _etf_agg(n: int) -> float:
        total_ratio = 0.0
        nonzero = 0
        for p in PRIMITIVE_KEYS:
            ep0 = float(intensities.get(p, 0.0))
            if ep0 > 0.0:
                total_ratio += etf_table[p][n] / ep0
                nonzero += 1
        return (total_ratio / nonzero) if nonzero > 0 else 0.0

    etf_agg_365   = _etf_agg(365)
    etf_agg_3650  = _etf_agg(3650)
    etf_agg_18250 = _etf_agg(18250)

    # §2 — state distribution + attractor.
    state_dist, attractor = compute_state_distribution(intensities)

    # §3 — collapse state.
    collapse_state = compute_collapse_state(
        state_dist, ep_field_summary, forecast_engine_layer, primitives_layer,
    )

    # §4 — P0-P8.
    p0_p8 = compute_p0_p8(state_dist, collapse_state, etf_agg_365, etf_agg_3650)

    # §5 — geography tier (only when a regional object is supplied).
    geography_tier = (
        compute_geography_tier(regional_object) if regional_object else None
    )

    # §6 — multiplier.
    field_intensity_scalar = float(ep_field_summary.get("intensity_mean") or 0.0)
    multiplier = compute_multiplier(
        field_intensity_scalar, state_dist["S4"], collapse_state,
    )

    # Pipeline block — map existing layers onto v2 L1-L10 ontology.
    pipeline = {
        "L1_ingest":    elins_object.get("input_phase") or {},
        "L2_normalize": {
            "normalized": True,
            "note": "_normalize() helper inside generate_ELINS; "
                    "no field surface in v33 output",
        },
        "L3_domain":    elins_object.get("domain_mapping") or {},
        "L4_narrative": elins_object.get("causal_chain") or {},
        "L5_pressure": {
            "primitive":  "pressure",
            "intensity":  float(intensities.get("pressure", 0.0)),
            "edge_count": edge_count.get("pressure", 0),
        },
        "L6_drift": {
            "primitive":  "drift",
            "intensity":  float(intensities.get("drift", 0.0)),
            "edge_count": edge_count.get("drift", 0),
        },
        "L7_basin": {
            "region":    region,
            "available": region is not None and regional_object is not None,
        },
        "L8_temporal": {
            "forecast_5day":   elins_object.get("forecast_5day") or {},
            "forecast_engine": elins_object.get("forecast_engine") or {},
            "etf_table":       {
                p: {str(n): etf_table[p][n] for n in HORIZONS_DAYS}
                for p in PRIMITIVE_KEYS
            },
            "etf_agg": {
                "n_365":   round(etf_agg_365, 6),
                "n_3650":  round(etf_agg_3650, 6),
                "n_18250": round(etf_agg_18250, 6),
            },
        },
        "L9_alignment": {
            "primitive":  "alignment",
            "intensity":  float(intensities.get("alignment", 0.0)),
            "edge_count": edge_count.get("alignment", 0),
        },
        "L10_signature": elins_object.get("output_object") or {},
    }

    outputs = {
        "collapse_state":     collapse_state,
        "attractor":          attractor,
        "state_distribution": state_dist,
        "P0_P8":              p0_p8,
        "geography_tier":     geography_tier,
        "timeline": {
            "short_term_days": 365,
            "mid_term_days":   3650,
            "long_term_days":  18250,
        },
        "multiplier":         multiplier,
    }

    return {
        "elins_version": ELINS_V2_VERSION,
        "region":        region,
        "input":         request_input or {},
        "pipeline":      pipeline,
        "outputs":       outputs,
        "meta": {
            "engine":    "clarity_elins_v2",
            "view_kind": "path_c_adapter",
            "warnings":  [],
            "notes":     [],
        },
    }
