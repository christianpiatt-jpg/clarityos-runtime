"""
v35 — Regional ELINS Modules + ESO-aware regional fields.

Region-aware wrapper around ``standard_elins.generate_ELINS``. Six regions
(US / EU / MEA / APAC / Markets / Tech) each get a hand-tuned profile that:

    * builds a region scaffold sentence the canonical pipeline can extract
      against (so callers don't have to author a scenario per region);
    * applies an entity-emphasis bump on top of the lexical extraction;
    * applies a domain-weighting overlay that nudges the effective top
      domain toward the region's natural cluster;
    * applies per-primitive λ adjustments routed through the v34
      forecast engine so the multi-envelope reflects regional decay;
    * optionally merges an ESO (External Signal Object) — when the caller
      supplies one, the ESO signals are blended in as an "external"
      class, surfaced explicitly in synthesis.external_anchors.

The function is pure with respect to its inputs (the canonical pipeline +
the ESO are both deterministic), so tests can pin behaviour exactly.

Public API:
    run_regional_elins(region_code, user, *, topic_hint=None, eso=None,
                       previous_run=None) -> dict
    REGION_CODES                          # supported regions
    REGION_PROFILES                       # static config per region
    EXTERNAL_PRIMITIVE_CLASS = "external"
"""
from __future__ import annotations

import time
from typing import Optional

from . import forecast_engine, standard_elins

REGION_CODES: tuple = ("US", "EU", "MEA", "APAC", "Markets", "Tech")
EXTERNAL_PRIMITIVE_CLASS: str = "external"


# ---------------------------------------------------------------------------
# Static per-region profile.
#
# scaffold:        a deterministic sentence the canonical pipeline can
#                  process when the caller doesn't supply a topic_hint
#                  (or supplies a thin one). The scaffold contains the
#                  region's natural lexical cluster so primitive
#                  extraction lights up the relevant fields.
# entity_terms:    entities that get an extra primitive-intensity bump
#                  when present in the input text.
# entity_bumps:    {primitive_key: float} — applied additively when any
#                  entity_term matches.
# domain_overlay:  domain weights merged onto the lexical mapping.
# lambda_overlay:  per-primitive λ overrides for the forecast engine.
# default_domain_hint: domain_hint passed into generate_ELINS.
# ---------------------------------------------------------------------------
REGION_PROFILES: dict[str, dict] = {
    "US": {
        "scaffold": (
            "United States policy environment: there is sustained pressure on the "
            "courts and growing tension between federal agencies. Trust in oversight "
            "is eroding under contradiction in messaging."
        ),
        "entity_terms": ["united states", "u.s.", "federal", "supreme court", "senate", "fed"],
        "entity_bumps": {"pressure": 0.06, "tension": 0.04, "contradiction": 0.04},
        "domain_overlay": {"institutional": 1.5, "legal": 1.3, "economic": 1.2},
        "lambda_overlay": {"pressure": 0.18, "contradiction": 0.22},
        "default_domain_hint": "institutional",
    },
    "EU": {
        "scaffold": (
            "European Union institutions face pressure on alignment between member "
            "states. Trust between partners is shifting and tension persists over "
            "regulation."
        ),
        "entity_terms": ["european union", "eu ", "brussels", "ecb", "european commission", "germany", "france"],
        "entity_bumps": {"alignment": 0.05, "tension": 0.03, "drift": 0.03},
        "domain_overlay": {"institutional": 1.4, "geopolitical": 1.2, "legal": 1.1},
        "lambda_overlay": {"alignment": 0.08, "drift": 0.05},
        "default_domain_hint": "institutional",
    },
    "MEA": {
        "scaffold": (
            "Middle East and Africa pressure is escalating with rising tension across "
            "alliances. Drift in regional posture and contradiction in stated policy "
            "raise stress on shipping and energy."
        ),
        "entity_terms": ["middle east", "iran", "saudi", "israel", "egypt", "mea", "gulf", "opec"],
        "entity_bumps": {"pressure": 0.08, "tension": 0.06, "drift": 0.04, "contradiction": 0.03},
        "domain_overlay": {"geopolitical": 1.6, "economic": 1.2, "ecological": 1.1},
        "lambda_overlay": {"pressure": 0.16, "tension": 0.16},
        "default_domain_hint": "geopolitical",
    },
    "APAC": {
        "scaffold": (
            "Asia Pacific posture is drifting with rising tension across the strait "
            "and shifting alignment among partners. Pressure is uneven across the "
            "region's economic blocs."
        ),
        "entity_terms": ["china", "japan", "korea", "taiwan", "asean", "apac", "asia pacific", "australia"],
        "entity_bumps": {"drift": 0.06, "tension": 0.04, "alignment": 0.04},
        "domain_overlay": {"geopolitical": 1.4, "technological": 1.2, "economic": 1.2},
        "lambda_overlay": {"drift": 0.04, "alignment": 0.09},
        "default_domain_hint": "geopolitical",
    },
    "Markets": {
        "scaffold": (
            "Global markets show pressure across risk assets and drift in yield curves. "
            "Trust between counterparties is intact but contradiction between forward "
            "guidance and pricing persists."
        ),
        "entity_terms": ["s&p", "nasdaq", "yield", "bond", "equity", "treasury", "fx", "ftse", "msci"],
        "entity_bumps": {"pressure": 0.06, "contradiction": 0.04, "drift": 0.03},
        "domain_overlay": {"economic": 1.6, "geopolitical": 1.0},
        "lambda_overlay": {"pressure": 0.22, "drift": 0.06},
        "default_domain_hint": "economic",
    },
    "Tech": {
        "scaffold": (
            "Technology sector shows drift toward frontier models and alignment around "
            "open-weight ecosystems. Tension remains over compute supply concentration."
        ),
        "entity_terms": ["ai", "model", "chip", "data center", "semiconductor", "openai", "anthropic", "platform"],
        "entity_bumps": {"drift": 0.06, "alignment": 0.04, "tension": 0.03},
        "domain_overlay": {"technological": 1.6, "economic": 1.2},
        "lambda_overlay": {"drift": 0.04, "alignment": 0.08},
        "default_domain_hint": "technological",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_region(region_code: str) -> str:
    if region_code not in REGION_CODES:
        raise ValueError(
            f"unknown region_code {region_code!r}; expected one of {REGION_CODES!r}"
        )
    return region_code


def _scenario_text_for(region_code: str, topic_hint: Optional[str]) -> str:
    profile = REGION_PROFILES[region_code]
    scaffold = profile["scaffold"]
    if topic_hint and isinstance(topic_hint, str):
        topic = topic_hint.strip()
        if topic:
            return f"{topic}. {scaffold}"
    return scaffold


def _apply_entity_bump(elins_obj: dict, region_code: str) -> dict:
    """Bump primitive intensities when region-defining entity terms appear
    in the input text. Returns the (mutated) ELINS object."""
    profile = REGION_PROFILES[region_code]
    text_lower = (
        elins_obj.get("input_phase", {}).get("text") or ""
    ).lower()
    if not any(term in text_lower for term in profile["entity_terms"]):
        return elins_obj
    intensities = elins_obj["primitives"]["intensities"]
    for k, bump in profile["entity_bumps"].items():
        if k in intensities:
            intensities[k] = round(min(1.0, float(intensities[k]) + float(bump)), 4)
    elins_obj["primitives"]["intensities"] = intensities
    return elins_obj


def _apply_domain_overlay(elins_obj: dict, region_code: str) -> dict:
    profile = REGION_PROFILES[region_code]
    dm = elins_obj.get("domain_mapping") or {}
    scores = dict(dm.get("scores") or {})
    for k, mult in profile["domain_overlay"].items():
        scores[k] = round(float(scores.get(k, 0.0) + 0.1) * float(mult), 4)
    if scores:
        nz = {k: v for k, v in scores.items() if v > 0.0}
        if nz:
            top = sorted(nz.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            dm["scores"] = nz
            dm["top"] = top
            # ``effective_top`` already preserves caller hint; only update if
            # the caller did not supply a hint.
            if not dm.get("hint"):
                dm["effective_top"] = top
    elins_obj["domain_mapping"] = dm
    return elins_obj


def _merge_eso(elins_obj: dict, eso: Optional[dict]) -> dict:
    """Blend an ESO (External Signal Object) into the ELINS record.

    Each ESO signal contributes additively to the matching primitive's
    intensity (capped at 1.0). The aggregate ESO contribution and the
    raw signal list are recorded under ``elins.external_signals`` so
    downstream consumers can attribute the bump.
    """
    if not eso:
        elins_obj["external_signals"] = {
            "present": False,
            "region_code": None,
            "anchors": [],
            "signals": [],
            "domain_bias": {},
        }
        return elins_obj
    signals = list(eso.get("signals") or [])
    anchors = list(eso.get("anchors") or [])
    domain_bias = dict(eso.get("domain_bias") or {})
    intensities = elins_obj["primitives"]["intensities"]
    contributions: dict[str, float] = {}
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        key = sig.get("key")
        if key not in intensities:
            continue
        try:
            intensity = float(sig.get("intensity") or 0.0)
            weight = float(sig.get("weight") or 1.0)
        except (TypeError, ValueError):
            continue
        bump = max(0.0, min(1.0, intensity * weight)) * 0.4
        contributions[key] = round(contributions.get(key, 0.0) + bump, 4)
        intensities[key] = round(min(1.0, float(intensities[key]) + bump), 4)
    elins_obj["primitives"]["intensities"] = intensities
    elins_obj["primitives"]["external_class"] = EXTERNAL_PRIMITIVE_CLASS
    # Domain bias overlay
    if domain_bias:
        dm = elins_obj.get("domain_mapping") or {}
        scores = dict(dm.get("scores") or {})
        for k, v in domain_bias.items():
            try:
                scores[k] = round(float(scores.get(k, 0.0)) + float(v), 4)
            except (TypeError, ValueError):
                continue
        if scores:
            nz = {k: v for k, v in scores.items() if v > 0.0}
            if nz:
                top = sorted(nz.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                dm["scores"] = nz
                dm["top"] = top
                if not dm.get("hint"):
                    dm["effective_top"] = top
        elins_obj["domain_mapping"] = dm
    elins_obj["external_signals"] = {
        "present": True,
        "region_code": eso.get("region_code"),
        "anchors": anchors,
        "signals": signals,
        "contributions": contributions,
        "domain_bias": domain_bias,
        "version": eso.get("version"),
        "mock": bool(eso.get("mock")),
    }
    return elins_obj


def _recompute_dependent_layers(elins_obj: dict, region_code: str) -> dict:
    """After mutating primitives + domain mapping + ESO, recompute the
    layers that derive from them so the synthesis surface is consistent."""
    primitives = elins_obj["primitives"]
    intensities = primitives["intensities"]

    # Layer 3 — EP field summary
    stress_keys = ("pressure", "tension", "drift", "contradiction")
    relief_keys = ("trust", "alignment")
    pos = sum(intensities.get(k, 0.0) for k in relief_keys)
    neg = sum(intensities.get(k, 0.0) for k in stress_keys)
    elins_obj["ep_field_summary"] = {
        "stress_total": round(neg, 4),
        "relief_total": round(pos, 4),
        "net": round(pos - neg, 4),
        "dominant": "relief" if pos > neg else ("stress" if neg > pos else "balanced"),
        "intensity_mean": round(
            sum(intensities.values()) / max(1, len(intensities)), 4,
        ),
    }

    # Layer 5 — stress/relief signal
    net = float(elins_obj["ep_field_summary"]["net"])
    if net > 0.15:
        signal = "relief_dominant"
    elif net < -0.15:
        signal = "stress_dominant"
    else:
        signal = "balanced"
    elins_obj["stress_relief"] = {
        "signal": signal,
        "net_pressure": round(-net, 4),
        "edge_count": (elins_obj.get("causal_chain") or {}).get("edge_count", 0),
    }

    # Forecast engine — recompute with regional λ overlay
    profile = REGION_PROFILES[region_code]
    lambda_overlay = dict(profile["lambda_overlay"])
    elins_obj["forecast_engine"] = forecast_engine.compute_forecast_block(
        intensities,
        edges=(elins_obj.get("causal_chain") or {}).get("edges") or [],
        days=5,
    )
    # Re-run with overlay-tuned λ values for primitives the region
    # profile cares about. We do this by recomputing per-primitive
    # envelopes + the multi-envelope using the overlaid λ values.
    primitives_list = []
    for key, intensity in intensities.items():
        primitives_list.append({
            "key": key,
            "intensity": intensity,
            "lambda": lambda_overlay.get(
                key, forecast_engine.DEFAULT_LAMBDAS.get(key, 0.15),
            ),
        })
    elins_obj["forecast_engine"]["primitive_envelopes"] = {
        p["key"]: forecast_engine.compute_envelope(p, days=5)
        for p in primitives_list
    }
    elins_obj["forecast_engine"]["multi_envelope"] = (
        forecast_engine.compute_multi_envelope(primitives_list, days=5)
    )
    elins_obj["forecast_engine"]["lambda_overlay"] = lambda_overlay
    elins_obj["forecast_engine"]["region_code"] = region_code

    # Synthesis — copy + extend with regional anchor info
    top_prim = sorted(intensities.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    domain_top = (elins_obj.get("domain_mapping") or {}).get("effective_top")
    syn = {
        "top_primitive": top_prim[0],
        "top_primitive_intensity": round(top_prim[1], 4),
        "domain": domain_top,
        "signal": elins_obj["stress_relief"]["signal"],
        "trend": (elins_obj.get("forecast_5day") or {}).get("trend", "flat"),
        "stress_score": elins_obj["ep_field_summary"]["stress_total"],
        "relief_score": elins_obj["ep_field_summary"]["relief_total"],
        "region_code": region_code,
        "external_anchors": list(
            (elins_obj.get("external_signals") or {}).get("anchors") or []
        ),
        "external_present": bool(
            (elins_obj.get("external_signals") or {}).get("present")
        ),
    }
    elins_obj["synthesis"] = syn

    # Output object mirror
    elins_obj["output_object"] = {
        "scenario_id": (elins_obj.get("input_phase") or {}).get("scenario_id"),
        "summary": syn,
        "ts": (elins_obj.get("input_phase") or {}).get("ts"),
        "version": "elins.regional.v35.1",
    }
    return elins_obj


def _attach_previous_run_delta(elins_obj: dict, previous_run: Optional[dict]) -> dict:
    if not previous_run:
        elins_obj["regional_delta"] = None
        return elins_obj
    prev_intensities = (previous_run.get("primitives") or {}).get("intensities") or {}
    cur_intensities = elins_obj["primitives"]["intensities"]
    deltas = {
        k: round(float(cur_intensities.get(k, 0.0)) - float(prev_intensities.get(k, 0.0)), 4)
        for k in cur_intensities.keys()
    }
    max_key = max(deltas.items(), key=lambda kv: abs(kv[1])) if deltas else (None, 0.0)
    elins_obj["regional_delta"] = {
        "deltas": deltas,
        "largest_shift_primitive": max_key[0],
        "largest_shift_value": max_key[1],
        "previous_scenario_id": (previous_run.get("output_object") or {}).get("scenario_id"),
    }
    return elins_obj


# ---------------------------------------------------------------------------
# Public — run_regional_elins
# ---------------------------------------------------------------------------
def run_regional_elins(
    region_code: str,
    user: Optional[str],
    *,
    topic_hint: Optional[str] = None,
    eso: Optional[dict] = None,
    previous_run: Optional[dict] = None,
) -> dict:
    """Run the canonical 10-layer ELINS pipeline + region-specific
    weighting + optional ESO blending. Returns the full ELINS object
    augmented with ``external_signals`` and ``regional_delta`` keys."""
    region = _validate_region(region_code)
    profile = REGION_PROFILES[region]
    text = _scenario_text_for(region, topic_hint)
    elins_obj = standard_elins.generate_ELINS(
        text,
        domain_hint=profile["default_domain_hint"],
        user=user,
    )
    elins_obj["region_code"] = region
    elins_obj["topic_hint"] = topic_hint
    _apply_entity_bump(elins_obj, region)
    _apply_domain_overlay(elins_obj, region)
    _merge_eso(elins_obj, eso)
    _recompute_dependent_layers(elins_obj, region)
    _attach_previous_run_delta(elins_obj, previous_run)
    elins_obj["regional_run_ts"] = (elins_obj.get("input_phase") or {}).get(
        "ts", time.time(),
    )
    return elins_obj
