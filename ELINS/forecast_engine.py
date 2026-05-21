"""
v34 — ELINS Forecast Engine (multi-primitive envelopes).

Pure, deterministic envelope math. NO model calls, NO random, NO state,
NO network. Same input → same output.

Core formula:
    ep(D+n) = ep0 * exp(-lambda * n)

Public API:
    compute_envelope(primitive, days=5)
    compute_multi_envelope(primitives, days=5)
    compute_domain_envelope(domain_vector, primitives, days=5)
    compute_chain_envelope(chain, days=5)

Each function returns a list of (days+1) floats — D+0 through D+days —
rounded to 6 decimal places.

Default ``lambda`` values are tuned per-primitive: stress primitives
(pressure, tension, contradiction) decay faster than relief primitives
(trust, alignment). Drift decays slowest because, by definition, it is
a slow vector-of-change. Callers can override ``lambda`` per primitive
by including ``"lambda": <float>`` in the primitive dict.

Helpers (also exported):
    build_primitives_from_intensities(intensities)
    build_chain_from_edges(edges, intensities)
    DEFAULT_LAMBDAS, DOMAIN_VECTORS, DOMAIN_NAMES
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
PRIMITIVE_KEYS: tuple = (
    "pressure",
    "tension",
    "trust",
    "drift",
    "contradiction",
    "alignment",
)

# Per-primitive decay constants. Tuned so that:
#  * pressure / tension / contradiction (acute stress) decay faster
#  * drift decays slowest (it is a long-running vector-of-change)
#  * trust / alignment (relief) decay slowly (relief is durable)
DEFAULT_LAMBDAS: dict[str, float] = {
    "pressure":      0.20,
    "tension":       0.18,
    "trust":         0.10,
    "drift":         0.05,
    "contradiction": 0.25,
    "alignment":     0.10,
}

# Spec-named macro domains. Each maps a primitive key to a non-negative
# weight; weights are normalized inside compute_domain_envelope.
DOMAIN_NAMES: tuple = (
    "Economic_Markets",
    "Geopolitical",
    "Social_Cultural",
    "Security_Military",
    "Legal_Justice",
    "Science_Technology",
    "Environmental",
)

DOMAIN_VECTORS: dict[str, dict[str, float]] = {
    "Economic_Markets": {
        "pressure":      0.40, "tension": 0.20, "trust": 0.15,
        "drift":         0.15, "contradiction": 0.05, "alignment": 0.05,
    },
    "Geopolitical": {
        "pressure":      0.30, "tension": 0.30, "trust": 0.10,
        "drift":         0.10, "contradiction": 0.10, "alignment": 0.10,
    },
    "Social_Cultural": {
        "pressure":      0.15, "tension": 0.20, "trust": 0.20,
        "drift":         0.20, "contradiction": 0.15, "alignment": 0.10,
    },
    "Security_Military": {
        "pressure":      0.35, "tension": 0.30, "trust": 0.05,
        "drift":         0.10, "contradiction": 0.10, "alignment": 0.10,
    },
    "Legal_Justice": {
        "pressure":      0.20, "tension": 0.20, "trust": 0.20,
        "drift":         0.15, "contradiction": 0.20, "alignment": 0.05,
    },
    "Science_Technology": {
        "pressure":      0.15, "tension": 0.10, "trust": 0.20,
        "drift":         0.25, "contradiction": 0.10, "alignment": 0.20,
    },
    "Environmental": {
        "pressure":      0.30, "tension": 0.15, "trust": 0.10,
        "drift":         0.30, "contradiction": 0.05, "alignment": 0.10,
    },
}

# Chain attenuation defaults. Applied to successive links so the
# forecast contribution of a primitive late in the chain is dampened.
DEFAULT_CHAIN_ATTENUATION: tuple = (1.00, 0.80, 0.65, 0.55, 0.50, 0.45)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _require_days(days) -> int:
    if not isinstance(days, int) or isinstance(days, bool):
        raise ValueError("days must be a positive int")
    if days < 1 or days > 30:
        raise ValueError("days must be in [1, 30]")
    return days


def _require_primitive(primitive) -> tuple[str, float, float]:
    if not isinstance(primitive, dict):
        raise ValueError("primitive must be a dict")
    key = primitive.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("primitive.key is required")
    intensity = primitive.get("intensity")
    if intensity is None:
        intensity = primitive.get("ep0")
    try:
        intensity = float(intensity)
    except (TypeError, ValueError) as exc:
        raise ValueError("primitive.intensity must be a float") from exc
    lam_raw = primitive.get("lambda")
    if lam_raw is None:
        lam = DEFAULT_LAMBDAS.get(key, 0.15)
    else:
        try:
            lam = float(lam_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("primitive.lambda must be a float") from exc
    if lam < 0.0:
        raise ValueError("primitive.lambda must be >= 0")
    return key, intensity, lam


def _round_list(xs: Iterable[float], places: int = 6) -> list[float]:
    return [round(float(x), places) for x in xs]


# ---------------------------------------------------------------------------
# 1 — single-primitive envelope
# ---------------------------------------------------------------------------
def compute_envelope(primitive: dict, days: int = 5) -> list[float]:
    """Return [ep(D+0), ep(D+1), ..., ep(D+days)] for a single primitive.

    ``primitive`` shape:  {"key": str, "intensity": float, "lambda"?: float}
    """
    n = _require_days(days)
    _, ep0, lam = _require_primitive(primitive)
    out = [ep0 * math.exp(-lam * step) for step in range(n + 1)]
    return _round_list(out)


# ---------------------------------------------------------------------------
# 2 — multi-primitive envelope (magnitude-weighted, normalized)
# ---------------------------------------------------------------------------
def compute_multi_envelope(primitives: list[dict], days: int = 5) -> list[float]:
    """Combined envelope across multiple primitives.

    Weighted by ``|intensity|``, normalized by the sum of magnitudes.
    Returns ``[ep(D+0), ..., ep(D+days)]``. If all magnitudes are zero,
    returns a flat zero array.
    """
    n = _require_days(days)
    if not isinstance(primitives, list):
        raise ValueError("primitives must be a list")
    parsed: list[tuple[str, float, float]] = [_require_primitive(p) for p in primitives]
    total_mag = sum(abs(p[1]) for p in parsed)
    if total_mag <= 0.0:
        return _round_list([0.0] * (n + 1))
    out: list[float] = []
    for step in range(n + 1):
        numer = sum(p[1] * math.exp(-p[2] * step) * abs(p[1]) for p in parsed)
        out.append(numer / total_mag)
    return _round_list(out)


# ---------------------------------------------------------------------------
# 3 — domain envelope (weighted by domain vector contribution)
# ---------------------------------------------------------------------------
def compute_domain_envelope(
    domain_vector: dict,
    primitives: list[dict],
    days: int = 5,
) -> list[float]:
    """Domain-specific forecast curve.

    ``domain_vector`` maps primitive_key -> non-negative weight. Primitives
    not present in the vector contribute zero. Returns ``[ep(D+0), ..., ep(D+days)]``.
    """
    n = _require_days(days)
    if not isinstance(domain_vector, dict):
        raise ValueError("domain_vector must be a dict")
    if not isinstance(primitives, list):
        raise ValueError("primitives must be a list")
    parsed: list[tuple[str, float, float]] = [_require_primitive(p) for p in primitives]
    weights: dict[str, float] = {}
    for k, v in domain_vector.items():
        try:
            w = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"domain_vector[{k!r}] must be a float") from exc
        if w < 0.0:
            raise ValueError(f"domain_vector[{k!r}] must be >= 0")
        weights[str(k)] = w
    total_w = sum(weights.values())
    if total_w <= 0.0:
        return _round_list([0.0] * (n + 1))
    out: list[float] = []
    for step in range(n + 1):
        numer = 0.0
        for key, ep0, lam in parsed:
            w = weights.get(key, 0.0)
            if w <= 0.0:
                continue
            numer += ep0 * math.exp(-lam * step) * w
        out.append(numer / total_w)
    return _round_list(out)


# ---------------------------------------------------------------------------
# 4 — chain envelope (causal chain with attenuation)
# ---------------------------------------------------------------------------
def compute_chain_envelope(chain: list[dict], days: int = 5) -> list[float]:
    """Chain-level forecast.

    ``chain`` is an ordered list of dicts; each link looks like::

        {"key": str, "intensity": float, "lambda"?: float, "attenuation"?: float}

    The link's contribution at step ``n`` is::

        attenuation * intensity * exp(-lambda * n)

    If ``attenuation`` is omitted, the position-default from
    ``DEFAULT_CHAIN_ATTENUATION`` is used (clamped to the last value if
    the chain is longer than the default tuple).

    The chain output is the SUM of link contributions per step (not a
    weighted average) — this is intentional, since chain coupling
    aggregates impact across the path rather than averaging it. Returns
    ``[ep(D+0), ..., ep(D+days)]``.
    """
    n = _require_days(days)
    if not isinstance(chain, list) or not chain:
        raise ValueError("chain must be a non-empty list")
    parsed: list[tuple[str, float, float, float]] = []
    for i, link in enumerate(chain):
        key, ep0, lam = _require_primitive(link)
        att_raw = link.get("attenuation")
        if att_raw is None:
            att = DEFAULT_CHAIN_ATTENUATION[
                min(i, len(DEFAULT_CHAIN_ATTENUATION) - 1)
            ]
        else:
            try:
                att = float(att_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"chain[{i}].attenuation must be a float"
                ) from exc
            if att < 0.0:
                raise ValueError(f"chain[{i}].attenuation must be >= 0")
        parsed.append((key, ep0, lam, att))
    out: list[float] = []
    for step in range(n + 1):
        s = sum(att * ep0 * math.exp(-lam * step) for _, ep0, lam, att in parsed)
        out.append(s)
    return _round_list(out)


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------
def build_primitives_from_intensities(
    intensities: dict,
    *,
    lambdas: Optional[dict] = None,
) -> list[dict]:
    """Convert ``{primitive_key: intensity}`` into the list shape the
    forecast functions accept. Stable order = ``PRIMITIVE_KEYS``."""
    if not isinstance(intensities, dict):
        raise ValueError("intensities must be a dict")
    out: list[dict] = []
    for key in PRIMITIVE_KEYS:
        if key not in intensities:
            continue
        try:
            v = float(intensities[key])
        except (TypeError, ValueError):
            continue
        lam = (lambdas or {}).get(key, DEFAULT_LAMBDAS.get(key, 0.15))
        out.append({"key": key, "intensity": v, "lambda": lam})
    return out


def build_chain_from_edges(
    edges: list[dict],
    intensities: dict,
    *,
    max_links: int = 4,
) -> Optional[list[dict]]:
    """Heuristic causal-chain builder.

    Take the highest-weight edges from the ELINS causal-chain layer and
    walk them into an ordered chain. Returns ``None`` when no chain can
    be assembled (no edges, or no overlapping nodes).

    Output shape: ``[{"key", "intensity", "lambda", "attenuation"}, ...]``.
    """
    if not isinstance(edges, list) or not edges:
        return None
    if not isinstance(intensities, dict):
        return None
    sorted_edges = sorted(
        (e for e in edges if isinstance(e, dict) and "from" in e and "to" in e),
        key=lambda e: -float(e.get("weight") or 0.0),
    )
    if not sorted_edges:
        return None
    # Greedy walk: start from the heaviest edge, keep adding edges that
    # extend the tail.
    head = sorted_edges[0]
    order: list[str] = [str(head["from"]), str(head["to"])]
    seen = set(order)
    used = {0}
    while len(order) < max_links:
        tail = order[-1]
        next_idx = None
        for idx, e in enumerate(sorted_edges):
            if idx in used:
                continue
            if str(e["from"]) == tail and str(e["to"]) not in seen:
                next_idx = idx
                break
            if str(e["to"]) == tail and str(e["from"]) not in seen:
                next_idx = idx
                # We're walking in reverse — flip the edge so the link
                # ordering remains tail→new.
                order.append(str(e["from"]))
                seen.add(str(e["from"]))
                used.add(idx)
                next_idx = -1
                break
        if next_idx is None:
            break
        if next_idx == -1:
            continue
        e = sorted_edges[next_idx]
        order.append(str(e["to"]))
        seen.add(str(e["to"]))
        used.add(next_idx)
    chain: list[dict] = []
    for i, key in enumerate(order):
        try:
            ep0 = float(intensities.get(key) or 0.0)
        except (TypeError, ValueError):
            ep0 = 0.0
        chain.append({
            "key": key,
            "intensity": ep0,
            "lambda": DEFAULT_LAMBDAS.get(key, 0.15),
            "attenuation": DEFAULT_CHAIN_ATTENUATION[
                min(i, len(DEFAULT_CHAIN_ATTENUATION) - 1)
            ],
        })
    return chain


# ---------------------------------------------------------------------------
# Composite — the dict shape standard_elins.generate_ELINS embeds under
# ``forecast_engine``. Pure function of (intensities, edges, days).
# ---------------------------------------------------------------------------
def compute_forecast_block(
    intensities: dict,
    *,
    edges: Optional[list] = None,
    days: int = 5,
) -> dict:
    """Return the full forecast_engine dict.

    Keys:
        primitive_envelopes  {primitive_key: [ep(D+0)..ep(D+days)]}
        multi_envelope       [ep(D+0)..ep(D+days)]
        domain_envelopes     {DOMAIN_NAME: [ep(D+0)..ep(D+days)]}
        chain                [{key, intensity, lambda, attenuation}, ...] or None
        chain_envelope       [ep(D+0)..ep(D+days)] or None
        days                 echo of the days argument
        version              "forecast.v34.1"
    """
    n = _require_days(days)
    primitives = build_primitives_from_intensities(intensities or {})

    primitive_envelopes: dict[str, list[float]] = {}
    for p in primitives:
        primitive_envelopes[p["key"]] = compute_envelope(p, days=n)

    multi_envelope = compute_multi_envelope(primitives, days=n)

    domain_envelopes: dict[str, list[float]] = {}
    for name in DOMAIN_NAMES:
        vec = DOMAIN_VECTORS[name]
        domain_envelopes[name] = compute_domain_envelope(vec, primitives, days=n)

    chain = build_chain_from_edges(edges or [], intensities or {})
    chain_env: Optional[list[float]] = None
    if chain:
        chain_env = compute_chain_envelope(chain, days=n)

    return {
        "primitive_envelopes": primitive_envelopes,
        "multi_envelope": multi_envelope,
        "domain_envelopes": domain_envelopes,
        "chain": chain,
        "chain_envelope": chain_env,
        "days": n,
        "version": "forecast.v34.1",
    }


# ---------------------------------------------------------------------------
# Static example for /elins/forecast/example
# ---------------------------------------------------------------------------
def example_payload() -> dict:
    """Static fixture for UI development. Returns a dict with the same
    shape that ``compute_forecast_block`` produces, plus the inputs
    that built it."""
    intensities = {
        "pressure":      0.85,
        "tension":       0.60,
        "trust":         0.20,
        "drift":         0.45,
        "contradiction": 0.50,
        "alignment":     0.15,
    }
    edges = [
        {"from": "pressure", "to": "tension", "weight": 0.60},
        {"from": "tension",  "to": "drift",   "weight": 0.45},
        {"from": "drift",    "to": "contradiction", "weight": 0.45},
    ]
    block = compute_forecast_block(intensities, edges=edges, days=5)
    return {
        "label": "Iran-style escalation chain",
        "inputs": {"intensities": intensities, "edges": edges, "days": 5},
        "forecast": block,
    }
