"""
v33 — Standardized ELINS 10-layer pipeline + S_ELINS QC.

Canonical pipeline shape (all stages return plain JSON-serializable
dicts; no embeddings, no model calls):

    0. Input phase            — accept + normalize raw text
    1. Primitive extraction   — six EP primitives extracted via lexicon
    2. Domain mapping         — keyword-to-domain weights
    3. EP field summary       — averaged primitive intensity + signs
    4. Causal chain mapping   — pairwise primitive co-occurrence
    5. Stress/relief signals  — net pressure (stress - relief)
    6. Five-day forecast      — deterministic phase trajectory
    7. Synthesis layer        — top-line summary fields
    8. QC layer (S_ELINS)     — re-extract + score alignment
    9. Output object          — final flat record

The implementation is intentionally LEXICAL + DETERMINISTIC: no
embeddings, no model calls, no network. Tests assert stable output
shapes for given inputs. Real integration with the embedding /
neighborhood layer happens in `app.py:_run_g_elins` (the v28 path);
this module is the canonical SCENARIO-TEXT pipeline that the
standardization spec requires every ELINS surface to produce.

Public API:
    generate_ELINS(input_text: str, *, domain_hint: Optional[str]=None,
                   user: Optional[str]=None) -> dict
    generate_S_ELINS(elins_object: dict) -> dict

Both return JSON-serialisable dicts; ``generate_S_ELINS`` re-runs
extraction + EP scoring on the original input recovered from the
ELINS object's `input_phase.text` and reports pass/fail + deltas.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Optional

from . import forecast_engine

# ---------------------------------------------------------------------------
# Layer + primitive identifiers
# ---------------------------------------------------------------------------
LAYER_NAMES: tuple = (
    "input_phase",
    "primitives",
    "domain_mapping",
    "ep_field_summary",
    "causal_chain",
    "stress_relief",
    "forecast_5day",
    "forecast_engine",
    "synthesis",
    "qc_s_elins",
    "output_object",
)

# Six EP primitives. Keep the keys stable — downstream consumers (Dewey,
# membership cohort metadata, the QC alignment scorer) depend on the names.
PRIMITIVE_KEYS: tuple = (
    "pressure",          # external force magnitude
    "tension",           # internal opposition
    "trust",             # cohesion / good-faith density
    "drift",             # vector-of-change toward a different state
    "contradiction",     # contradictory signals in the same field
    "alignment",         # convergence / shared direction
)

# Lexicon — deliberately small + well-bounded so the extraction is
# transparent. Keys are lowercase substrings; values are the primitive
# they bump and the increment per match. Tunable; tests pin behavior on
# specific inputs so changes here surface immediately.
_PRIMITIVE_LEXICON: dict[str, list[tuple[str, float]]] = {
    "pressure":      [("pressure", 0.4), ("force", 0.3), ("strain", 0.3),
                      ("squeeze", 0.3), ("urgent", 0.2), ("crisis", 0.4),
                      ("collapse", 0.5), ("escalat", 0.4)],
    "tension":       [("tension", 0.4), ("conflict", 0.3), ("dispute", 0.3),
                      ("oppos", 0.3), ("argu", 0.2), ("clash", 0.3),
                      ("stand-off", 0.4), ("standoff", 0.4)],
    "trust":         [("trust", 0.4), ("confidence", 0.3), ("loyalt", 0.3),
                      ("integrity", 0.3), ("bond", 0.2), ("good faith", 0.4),
                      ("reliable", 0.3), ("credibilit", 0.3)],
    "drift":         [("drift", 0.4), ("erod", 0.3), ("shift", 0.3),
                      ("slid", 0.3), ("deteriorat", 0.4), ("decline", 0.3),
                      ("trend toward", 0.4), ("away from", 0.3)],
    "contradiction": [("contradict", 0.4), ("hypocris", 0.4), ("inconsis", 0.4),
                      ("paradox", 0.3), ("but also", 0.2), ("yet", 0.1),
                      ("at odds", 0.3), ("doublethink", 0.4)],
    "alignment":     [("align", 0.4), ("agree", 0.3), ("converg", 0.3),
                      ("cooperat", 0.3), ("consensus", 0.3), ("shared", 0.2),
                      ("united", 0.3), ("partner", 0.2)],
}

# Domain heuristic — same lexical pattern, mapped to the canonical
# domains the spec calls out. Tests pin a few representative inputs.
DOMAIN_HINTS: tuple = (
    "legal",
    "institutional",
    "economic",
    "geopolitical",
    "social",
    "personal",
    "technological",
    "ecological",
)

_DOMAIN_LEXICON: dict[str, list[str]] = {
    "legal":          ["law", "court", "judge", "ruling", "constitut", "statute",
                       "legal", "litigat", "supreme court", "judic"],
    "institutional":  ["institution", "agency", "regulat", "ministr", "bureau",
                       "oversight", "compliance", "governance", "watchdog"],
    "economic":       ["econom", "market", "inflat", "supply", "demand",
                       "tariff", "trade", "currenc", "fiscal", "monetary",
                       "deficit", "growth", "recession"],
    "geopolitical":   ["china", "russia", "us-", "u.s.", "nato", "border",
                       "alliance", "diploma", "sanction", "treaty", "war"],
    "social":         ["public", "voter", "protest", "movement", "communit",
                       "popular", "social", "media coverage", "sentiment"],
    "personal":       ["i ", "my ", "feel", "myself", "we ", "our ", "she ", "he ",
                       "they ", "personal"],
    "technological":  ["ai ", "model", "algorithm", "platform", "infrastructure",
                       "software", "chip", "data center"],
    "ecological":     ["climate", "carbon", "emission", "ecolog", "environment",
                       "drought", "biodivers", "energy supply"],
}

# Stress vs. relief separation — used by Layer 5. Stress primitives push
# the system toward instability; relief primitives push toward stability.
STRESS_PRIMITIVES = ("pressure", "tension", "drift", "contradiction")
RELIEF_PRIMITIVES = ("trust", "alignment")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("input must be a string")
    s = text.strip()
    if not s:
        raise ValueError("input must be non-empty")
    return s


def _scenario_id(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sc_{h[:16]}"


def _count_matches(text_lower: str, lexicon: dict) -> dict:
    """For each key in ``lexicon``, sum match weights present in the
    text. Accepts both lexicon shapes used in this module:
    ``list[(token, weight)]`` (primitive lexicon) or plain
    ``list[str]`` (domain lexicon — every match weighs 1.0)."""
    out: dict[str, float] = {k: 0.0 for k in lexicon.keys()}
    for key, entries in lexicon.items():
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                token, weight = entry
            else:
                token, weight = entry, 1.0
            if token in text_lower:
                # Count multiple occurrences (cap at 5 per token to bound
                # output range without thresholding the lexicon further).
                hits = min(5, text_lower.count(token))
                out[key] += float(weight) * hits
    return out


def _round_dict(d: dict, places: int = 4) -> dict:
    return {k: round(float(v), places) for k, v in d.items()}


def _domain_top(scores: dict) -> tuple[Optional[str], dict]:
    """Pick the highest-scoring domain. Ties are broken alphabetically so
    the output is deterministic."""
    nz = {k: v for k, v in scores.items() if v > 0.0}
    if not nz:
        return None, {}
    top = sorted(nz.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return top, _round_dict(nz)


# ---------------------------------------------------------------------------
# Per-layer functions (numbered to match the spec)
# ---------------------------------------------------------------------------
def _layer_0_input(text: str, *, domain_hint: Optional[str], user: Optional[str]) -> dict:
    return {
        "scenario_id": _scenario_id(text),
        "text": text,
        "char_count": len(text),
        "word_count": len(text.split()),
        "domain_hint": domain_hint,
        "user": user,
        "ts": time.time(),
    }


def _layer_1_primitives(text: str) -> dict:
    """Six-primitive extraction. Returns raw match counts + a
    normalized [0..1] intensity per primitive."""
    text_lower = text.lower()
    raw = _count_matches(text_lower, _PRIMITIVE_LEXICON)
    # Normalize: divide by 4.0 (a reasonable upper bound given the
    # weights + cap of 5 occurrences) and clip to [0..1].
    intensities = {k: max(0.0, min(1.0, v / 4.0)) for k, v in raw.items()}
    return {
        "raw_scores": _round_dict(raw),
        "intensities": _round_dict(intensities),
        "primitive_keys": list(PRIMITIVE_KEYS),
    }


def _layer_2_domains(text: str, hint: Optional[str]) -> dict:
    text_lower = text.lower()
    matches = _count_matches(text_lower, _DOMAIN_LEXICON)
    top, scores = _domain_top(matches)
    if hint and hint in DOMAIN_HINTS:
        # Caller hint nudges but does not override; record both.
        return {
            "scores": scores,
            "top": top,
            "hint": hint,
            "effective_top": hint if top is None else top,
        }
    return {"scores": scores, "top": top, "hint": None, "effective_top": top}


def _layer_3_ep_summary(primitives: dict) -> dict:
    intensities = primitives["intensities"]
    # Net signed value: relief primitives count positive; stress primitives
    # count negative. Bounded by the count of primitive groups.
    pos = sum(intensities[k] for k in RELIEF_PRIMITIVES)
    neg = sum(intensities[k] for k in STRESS_PRIMITIVES)
    return {
        "stress_total": round(neg, 4),
        "relief_total": round(pos, 4),
        "net": round(pos - neg, 4),
        "dominant": "relief" if pos > neg else ("stress" if neg > pos else "balanced"),
        "intensity_mean": round(sum(intensities.values()) / len(intensities), 4),
    }


def _layer_4_causal_chain(primitives: dict) -> dict:
    """Pairwise co-occurrence — surfaces which pairs of primitives are
    BOTH present at meaningful intensity. Threshold: 0.05."""
    intensities = primitives["intensities"]
    pairs = []
    threshold = 0.05
    keys = list(PRIMITIVE_KEYS)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ia, ib = intensities[a], intensities[b]
            if ia >= threshold and ib >= threshold:
                pairs.append({
                    "from": a, "to": b,
                    "weight": round(min(ia, ib), 4),
                })
    pairs.sort(key=lambda p: -p["weight"])
    return {
        "edges": pairs,
        "edge_count": len(pairs),
        "threshold": threshold,
    }


def _layer_5_stress_relief(ep_summary: dict, causal: dict) -> dict:
    net = float(ep_summary["net"])
    if net > 0.15:
        signal = "relief_dominant"
    elif net < -0.15:
        signal = "stress_dominant"
    else:
        signal = "balanced"
    return {
        "signal": signal,
        "net_pressure": round(-net, 4),  # +ve = system is stressed
        "edge_count": causal["edge_count"],
    }


def _layer_6_forecast_5day(ep_summary: dict, stress_relief: dict) -> dict:
    """Deterministic phase trajectory. Each day's bias is the previous day's
    net plus a small mean-reversion component. No randomness."""
    base = float(ep_summary["net"])
    days = []
    cur = base
    for d in range(1, 6):
        # Mean-revert toward 0 by 12% per step; add a small "drift" term
        # equal to half of the contradiction intensity so contradictions
        # extend the stress trajectory a bit longer.
        cur = round(cur - cur * 0.12, 4)
        days.append({
            "day": d,
            "projected_net": cur,
            "phase": "relief" if cur > 0.05 else ("stress" if cur < -0.05 else "balanced"),
        })
    return {
        "days": days,
        "starting_net": round(base, 4),
        "ending_net": days[-1]["projected_net"],
        "trend": (
            "easing" if days[-1]["projected_net"] > base + 0.01
            else "tightening" if days[-1]["projected_net"] < base - 0.01
            else "flat"
        ),
    }


def _layer_7_synthesis(layers: dict) -> dict:
    """Top-line summary fields. Pure functions of earlier layers; no new
    inference."""
    primitives = layers["primitives"]["intensities"]
    domain = layers["domain_mapping"]
    ep = layers["ep_field_summary"]
    sr = layers["stress_relief"]
    forecast = layers["forecast_5day"]
    # Top-1 primitive (alphabetical tiebreak for determinism).
    top_prim = sorted(primitives.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {
        "top_primitive": top_prim[0],
        "top_primitive_intensity": round(top_prim[1], 4),
        "domain": domain.get("effective_top"),
        "signal": sr["signal"],
        "trend": forecast["trend"],
        "stress_score": round(ep["stress_total"], 4),
        "relief_score": round(ep["relief_total"], 4),
    }


def _layer_8_qc_self(text: str, layers: dict) -> dict:
    """Inline self-QC — re-extract primitives once, compare to the
    primary extraction. Not the same as the public ``generate_S_ELINS``
    (which takes the full ELINS object); this one is a sanity check
    embedded in the main pipeline."""
    second = _layer_1_primitives(text)
    deltas = {
        k: round(layers["primitives"]["intensities"][k] - second["intensities"][k], 4)
        for k in PRIMITIVE_KEYS
    }
    max_delta = max(abs(v) for v in deltas.values()) if deltas else 0.0
    return {
        "self_check": "stable" if max_delta < 1e-6 else "unstable",
        "max_delta": max_delta,
        "deltas": deltas,
    }


def _layer_9_output(layers: dict) -> dict:
    """Flat output mirror — copies the synthesis fields onto the top
    level of the ELINS object so downstream consumers don't have to
    walk the full record."""
    syn = layers["synthesis"]
    return {
        "scenario_id": layers["input_phase"]["scenario_id"],
        "summary": syn,
        "ts": layers["input_phase"]["ts"],
        "version": "elins.v34.1",
    }


# ---------------------------------------------------------------------------
# Public — generate_ELINS
# ---------------------------------------------------------------------------
def generate_ELINS(
    input_text: str,
    *,
    domain_hint: Optional[str] = None,
    user: Optional[str] = None,
) -> dict:
    """Run the canonical 10-layer ELINS pipeline. Returns a flat dict
    with every layer present + an ``output_object`` mirror. Raises
    ValueError on bad input."""
    text = _normalize(input_text)
    if domain_hint is not None and domain_hint not in DOMAIN_HINTS:
        raise ValueError(
            f"domain_hint must be one of {DOMAIN_HINTS!r}, got {domain_hint!r}"
        )
    layers: dict = {}
    layers["input_phase"] = _layer_0_input(text, domain_hint=domain_hint, user=user)
    layers["primitives"] = _layer_1_primitives(text)
    layers["domain_mapping"] = _layer_2_domains(text, domain_hint)
    layers["ep_field_summary"] = _layer_3_ep_summary(layers["primitives"])
    layers["causal_chain"] = _layer_4_causal_chain(layers["primitives"])
    layers["stress_relief"] = _layer_5_stress_relief(
        layers["ep_field_summary"], layers["causal_chain"],
    )
    layers["forecast_5day"] = _layer_6_forecast_5day(
        layers["ep_field_summary"], layers["stress_relief"],
    )
    # v34 — multi-primitive envelope forecast layer. Pure function of the
    # extracted intensities + causal edges; no model calls.
    layers["forecast_engine"] = forecast_engine.compute_forecast_block(
        layers["primitives"]["intensities"],
        edges=layers["causal_chain"]["edges"],
        days=5,
    )
    layers["synthesis"] = _layer_7_synthesis(layers)
    layers["qc_s_elins"] = _layer_8_qc_self(text, layers)
    layers["output_object"] = _layer_9_output(layers)
    layers["layer_names"] = list(LAYER_NAMES)
    return layers


# ---------------------------------------------------------------------------
# Public — generate_S_ELINS
# ---------------------------------------------------------------------------
def generate_S_ELINS(elins_object: dict) -> dict:
    """Re-extract primitives from the original input, recompute the EP
    field summary, and report pass/fail + per-primitive deltas.

    Pass criterion: max absolute delta across all six primitives is
    below ``S_ELINS_PASS_THRESHOLD`` (default 0.05). Stable + lexical
    extraction means this should always pass for unchanged inputs;
    failures indicate the ELINS object was edited or partially built."""
    if not isinstance(elins_object, dict):
        raise ValueError("elins_object must be a dict")
    input_phase = elins_object.get("input_phase") or {}
    text = input_phase.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("elins_object.input_phase.text is required")

    fresh_primitives = _layer_1_primitives(text)
    fresh_ep = _layer_3_ep_summary(fresh_primitives)

    original_intensities = (
        (elins_object.get("primitives") or {}).get("intensities") or {}
    )
    deltas = {
        k: round(
            float(fresh_primitives["intensities"][k])
            - float(original_intensities.get(k, 0.0)),
            4,
        )
        for k in PRIMITIVE_KEYS
    }
    max_delta = max(abs(v) for v in deltas.values()) if deltas else 0.0
    # Alignment score: 1.0 when deltas are all zero, decays linearly.
    alignment = max(0.0, 1.0 - max_delta * 4.0)
    threshold = S_ELINS_PASS_THRESHOLD
    return {
        "ok": True,
        "scenario_id": (elins_object.get("output_object") or {}).get("scenario_id")
                        or _scenario_id(text),
        "alignment_score": round(alignment, 4),
        "max_delta": round(max_delta, 4),
        "deltas": deltas,
        "fresh_primitives": fresh_primitives["intensities"],
        "fresh_ep_summary": fresh_ep,
        "passed": max_delta < threshold,
        "threshold": threshold,
        "version": "selins.v33.1",
        "ts": time.time(),
    }


S_ELINS_PASS_THRESHOLD: float = 0.05
