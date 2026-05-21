"""
v52 — Region metrics for Universal Physics validation.

Pure deterministic helpers that compute the M1/M2/M3 protocol observables
from existing ELINS data structures:

    E                    = envelope-integrated stress mass per region
    r                    = graph radius of the induced subgraph
    triangle_homogeneity = mean (1 - CV) over triads in the subgraph
    orientation_score    = relief / (relief + stress) over the runs
    node_count           = entities in the region's cluster

Orientation intervention: re-evaluate every per-run scalar with stress-
primitive lambdas multiplied by (1 + ORIENTATION_LAMBDA_BUMP). Higher
lambda = faster envelope decay, so post-orientation E and envelope-
weighted edge contributions both shrink. The graph topology does not
change; only the edge weights and E values do, so triangle_homogeneity
and triangle_density move while node_count and r are stable.

This module is a v52 *measurement* layer — it does not mutate any
existing ELINS object and adds no new public endpoints.

Public API:
    STRESS_PRIMS, RELIEF_PRIMS, HORIZON_DAYS, ORIENTATION_LAMBDA_BUMP
    envelope_integral(elins_run, *, oriented=False)
    orientation_lambdas(*, bump=ORIENTATION_LAMBDA_BUMP)
    stress_mass(elins_run)
    relief_mass(elins_run)
    orientation_score(runs)
    build_envelope_weighted_graph(elins_runs, *, oriented=False)
    induced_subgraph(graph, region_label)
    graph_radius(entities, edges)
    find_triangles(entities, edges)
    triangle_homogeneity(triangles, edges)
    region_metrics_row(region_label, runs, graph_pre, graph_post)
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Iterable, Optional

from . import forecast_engine
from . import standard_elins  # for PRIMITIVE_KEYS only

STRESS_PRIMS: tuple = ("pressure", "tension", "drift", "contradiction")
RELIEF_PRIMS: tuple = ("alignment", "trust")
HORIZON_DAYS: int = 5
ORIENTATION_LAMBDA_BUMP: float = 0.5  # +50% to stress lambdas under orientation

# v52.2 — scale-sensitive DV constants (per spec).
THRESHOLD_QUANTILE: float = 0.25  # weak-triangle threshold (lower edge quantile)
EPS: float = 1e-12                # safe-divide floor for percent-change
INV_ALPHA: float = 0.5            # exponent for inverse-weight triangle sum
INV_C: float = 1e-6               # additive regulariser before reciprocal

METRICS_VERSION: str = "region_metrics.v52.2"


# ---------------------------------------------------------------------------
# Per-run scalars
# ---------------------------------------------------------------------------
def _intensities(elins_run: dict) -> dict:
    if not isinstance(elins_run, dict):
        return {}
    prim = elins_run.get("primitives") or {}
    intens = prim.get("intensities") or {}
    if isinstance(intens, dict) and intens:
        return intens
    # save_regional_run stores the raw intensity map at top level too
    flat = elins_run.get("primitives")
    if isinstance(flat, dict) and "intensities" not in flat:
        return flat
    return {}


def stress_mass(elins_run: dict) -> float:
    intens = _intensities(elins_run)
    return float(sum(float(intens.get(k, 0.0) or 0.0) for k in STRESS_PRIMS))


def relief_mass(elins_run: dict) -> float:
    intens = _intensities(elins_run)
    return float(sum(float(intens.get(k, 0.0) or 0.0) for k in RELIEF_PRIMS))


def envelope_integral(
    elins_run: dict,
    *,
    horizon: int = HORIZON_DAYS,
    lambdas: Optional[dict] = None,
    oriented: bool = False,
) -> float:
    """Discrete sum of stress envelopes ep0 * exp(-lambda * day) over
    day = 0 .. horizon, summed across the four stress primitives."""
    if oriented:
        lambdas = orientation_lambdas(default=lambdas)
    intens = _intensities(elins_run)
    total = 0.0
    for key in STRESS_PRIMS:
        ep0 = float(intens.get(key, 0.0) or 0.0)
        if ep0 == 0.0:
            continue
        if lambdas and key in lambdas:
            lam = float(lambdas[key])
        else:
            lam = float(forecast_engine.DEFAULT_LAMBDAS.get(key, 0.15))
        for d in range(int(horizon) + 1):
            total += ep0 * math.exp(-lam * d)
    return total


def orientation_lambdas(
    *,
    default: Optional[dict] = None,
    bump: float = ORIENTATION_LAMBDA_BUMP,
) -> dict:
    """Lambda overlay where stress primitives decay (1 + bump) faster.
    Relief primitives are left unchanged."""
    base = dict(default or forecast_engine.DEFAULT_LAMBDAS)
    out = dict(base)
    for k in STRESS_PRIMS:
        if k in out:
            out[k] = float(out[k]) * (1.0 + float(bump))
    return out


def orientation_score(runs: Iterable[dict]) -> float:
    """relief / (relief + stress) over a set of runs. Bounded [0, 1].
    Empty input returns 0.0."""
    runs = list(runs or [])
    if not runs:
        return 0.0
    rel = sum(relief_mass(r) for r in runs)
    stress = sum(stress_mass(r) for r in runs)
    total = rel + stress
    return float(rel / total) if total > 0 else 0.0


def conflict_mass_E(runs: Iterable[dict], *, oriented: bool = False) -> float:
    """E = sum of envelope-integrated stress over the runs."""
    runs = list(runs or [])
    if not runs:
        return 0.0
    return float(sum(envelope_integral(r, oriented=oriented) for r in runs))


# ---------------------------------------------------------------------------
# Envelope-weighted graph
# ---------------------------------------------------------------------------
def _entities_of(elins_run: dict) -> list[str]:
    """Prefer the canonical elins_entity_graph extractor for parity with
    the production graph. Tests can short-circuit with a pre-extracted
    list at elins_run['_extracted_entities']."""
    cached = elins_run.get("_extracted_entities")
    if cached is not None:
        return [str(x) for x in cached]
    try:
        import elins_entity_graph as _eg  # repo-root module
        rows = _eg.extract_entities(elins_run) or []
        return [r["name"] for r in rows if isinstance(r, dict) and r.get("name")]
    except Exception:
        pass
    # Minimal fallback — anchors + topic_hint only.
    out: list[str] = []
    seen: set = set()

    def _add(name):
        s = str(name or "").strip()
        low = s.lower()
        if low and low not in seen:
            seen.add(low)
            out.append(s)

    ext = elins_run.get("external_signals") or {}
    for a in (ext.get("anchors") or []):
        _add(a)
    syn = elins_run.get("synthesis") or {}
    for a in (syn.get("external_anchors") or []):
        _add(a)
    th = elins_run.get("topic_hint")
    if isinstance(th, str) and th.strip():
        _add(th)
    return out


def _cluster_of(elins_run: dict) -> str:
    rc = elins_run.get("region_code")
    if isinstance(rc, str) and rc:
        return rc
    return "global"


def build_envelope_weighted_graph(
    elins_runs: Iterable[dict],
    *,
    oriented: bool = False,
) -> dict:
    """Build a graph in the style of elins_entity_graph but where each
    co-occurrence contributes the run's envelope-integrated stress
    instead of ep_field_summary.intensity_mean. Edge weight is the sum
    of these contributions (plus 1.0 base per co-occurrence so low-
    stress runs still register). Topology is identical for oriented
    vs default; only edge weights differ.
    """
    graph = {
        "entities": {},
        "edges": {},
        "version": METRICS_VERSION,
        "oriented": bool(oriented),
    }
    runs = list(elins_runs or [])
    for run in runs:
        ents = _entities_of(run)
        if not ents:
            continue
        cluster = _cluster_of(run)
        env = envelope_integral(run, oriented=oriented)
        for name in ents:
            rec = graph["entities"].setdefault(name, {
                "clusters": [],
                "appearances": 0,
                "stress_sum": 0.0,
            })
            if cluster not in rec["clusters"]:
                rec["clusters"].append(cluster)
            rec["appearances"] += 1
            rec["stress_sum"] = round(rec["stress_sum"] + env, 4)
        # pairwise edges, lex-sorted dedupe
        names = sorted(set(ents))
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                key = f"{a}||{b}"
                edge = graph["edges"].setdefault(key, {
                    "a": a, "b": b,
                    "weight": 0.0,
                    "co_occurrences": 0,
                })
                edge["co_occurrences"] += 1
                edge["weight"] = round(edge["weight"] + 1.0 + env, 4)
    return graph


def induced_subgraph(graph: dict, region_label: str) -> tuple:
    """Return (entities, edges) where both endpoints belong to the
    region's cluster set."""
    if not isinstance(graph, dict):
        return set(), {}
    ents = {
        name for name, rec in (graph.get("entities") or {}).items()
        if region_label in (rec.get("clusters") or [])
    }
    edges = {
        k: e for k, e in (graph.get("edges") or {}).items()
        if e["a"] in ents and e["b"] in ents
    }
    return ents, edges


def graph_radius(entities: set, edges: dict) -> int:
    """Max eccentricity over connected components. Disconnected
    components contribute their own internal max; the overall radius
    is the largest of those (i.e., the diameter of the largest CC).
    Returns 0 for empty graphs and 1 for singletons.
    """
    if not entities:
        return 0
    if len(entities) == 1:
        return 1
    adj: dict = defaultdict(set)
    for e in edges.values():
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])

    def bfs_eccentricity(start: str) -> int:
        seen = {start: 0}
        q: deque = deque([start])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen[v] = seen[u] + 1
                    q.append(v)
        return max(seen.values()) if seen else 0

    eccs = [bfs_eccentricity(n) for n in entities]
    return max(eccs) if eccs else 1


def find_triangles(entities: set, edges: dict) -> list:
    """Enumerate 3-cliques. Returns sorted (a, b, c) tuples."""
    adj: dict = defaultdict(set)
    for e in edges.values():
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    ents = sorted(entities)
    triangles: list = []
    idx = {name: i for i, name in enumerate(ents)}
    for a in ents:
        for b in adj[a]:
            if idx.get(b, -1) <= idx.get(a, -1):
                continue
            common = adj[a] & adj[b]
            for c in common:
                if idx.get(c, -1) <= idx.get(b, -1):
                    continue
                triangles.append((a, b, c))
    return triangles


def _edge_weight(edges: dict, x: str, y: str) -> float:
    a, b = (x, y) if x < y else (y, x)
    rec = edges.get(f"{a}||{b}")
    if rec is None:
        return 0.0
    return float(rec.get("weight") or 0.0)


def edge_weights_list(edges: dict) -> list[float]:
    return [float(e.get("weight") or 0.0) for e in edges.values()]


def quantile(xs: list[float], q: float) -> float:
    """Linear-interpolated quantile. Returns 0.0 on empty input."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    q = max(0.0, min(1.0, float(q)))
    k = q * (len(s) - 1)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return float(s[lo] + frac * (s[hi] - s[lo]))


def mean_edge_weight(edges: dict) -> float:
    ws = edge_weights_list(edges)
    return float(sum(ws) / len(ws)) if ws else 0.0


def triangle_total_weight(triangles: list, edges: dict) -> float:
    """Sum of edge weights across all listed triangles. Each triangle
    contributes its three edge weights."""
    total = 0.0
    for (a, b, c) in triangles:
        total += _edge_weight(edges, a, b)
        total += _edge_weight(edges, a, c)
        total += _edge_weight(edges, b, c)
    return float(total)


def weak_triangles(
    triangles: list,
    edges: dict,
    *,
    threshold_quantile: float = THRESHOLD_QUANTILE,
    threshold: Optional[float] = None,
) -> list:
    """Triangles whose minimum edge weight is below the given quantile of
    all region edge weights. If `threshold` is supplied, it overrides
    the quantile-derived threshold (lets callers freeze the threshold
    from the pre-graph and reuse it on the post-graph)."""
    if not triangles:
        return []
    if threshold is None:
        ws = edge_weights_list(edges)
        threshold = quantile(ws, threshold_quantile)
    out: list = []
    for (a, b, c) in triangles:
        ws3 = (
            _edge_weight(edges, a, b),
            _edge_weight(edges, a, c),
            _edge_weight(edges, b, c),
        )
        if min(ws3) < float(threshold):
            out.append((a, b, c))
    return out


def triangle_inv_weight(
    triangles: list,
    edges: dict,
    *,
    alpha: float = INV_ALPHA,
    c: float = INV_C,
) -> float:
    """Sum over triangles of (mean_triangle_edge + c)^(-alpha). Captures
    'fragility' — weak-mean triangles contribute more. Regularised
    by `c` so vanishing edge weights don't blow up."""
    if not triangles:
        return 0.0
    total = 0.0
    for (a, b, k) in triangles:
        m = (
            _edge_weight(edges, a, b)
            + _edge_weight(edges, a, k)
            + _edge_weight(edges, b, k)
        ) / 3.0
        total += (m + float(c)) ** (-float(alpha))
    return float(total)


def safe_pct_change(post: float, pre: float, *, eps: float = EPS) -> float:
    """Percent change with safe-divide. When |pre| <= eps we use eps
    as the denominator (signed) so the result is finite but signals
    'large relative change' on near-zero baselines."""
    if abs(pre) > eps:
        return float((post - pre) / pre)
    denom = eps if pre >= 0 else -eps
    return float((post - pre) / denom)


def triangle_homogeneity(triangles: list, edges: dict) -> float:
    """Mean (1 - CV) over triads, where CV = stdev(weights) / mean(weights).
    Bounded to [0, 1]: a perfectly equilateral triangle scores 1.0; a
    triangle with one dominant edge approaches 0.
    """
    if not triangles:
        return 0.0
    homogs: list = []
    for (a, b, c) in triangles:
        w_ab = _edge_weight(edges, a, b)
        w_ac = _edge_weight(edges, a, c)
        w_bc = _edge_weight(edges, b, c)
        ws = [w_ab, w_ac, w_bc]
        m = sum(ws) / 3.0
        if m <= 0:
            continue
        var = sum((x - m) ** 2 for x in ws) / 3.0
        std = math.sqrt(var)
        cv = std / m
        homogs.append(max(0.0, 1.0 - cv))
    if not homogs:
        return 0.0
    return float(sum(homogs) / len(homogs))


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------
def region_metrics_row(
    region_label: str,
    runs_in_region: Iterable[dict],
    graph_pre: dict,
    graph_post: dict,
) -> dict:
    """Compute the full M1/M2/M3 row for one (region | timestep).

    Returns the legacy homogeneity-based delta (kept for backward
    compatibility) plus the v52.2 scale-sensitive DVs:

        delta_total_weight       sum(post triangle weights) - sum(pre)
        delta_pct_total          (post - pre) / pre, safe-divided
        delta_total_weak         same restricted to weak triangles
        delta_pct_total_weak     pct-change form on weak-triangle sum
        delta_mean_edge          mean edge-weight difference
        delta_inv_weight         inverse-weight triangle sum difference

    Weak-triangle identification uses the *pre* graph; the same triangle
    set is then summed over the post graph so weak/strong split is
    stable across the orientation step.
    """
    runs_in_region = list(runs_in_region or [])
    ents_pre, edges_pre = induced_subgraph(graph_pre, region_label)
    ents_post, edges_post = induced_subgraph(graph_post, region_label)
    ents = ents_pre  # topology identical pre/post by construction
    triangles = find_triangles(ents, edges_pre)

    # Legacy DV
    th_pre = triangle_homogeneity(triangles, edges_pre)
    th_post = triangle_homogeneity(triangles, edges_post)

    # v52.2 scale-sensitive DVs
    tw_pre = triangle_total_weight(triangles, edges_pre)
    tw_post = triangle_total_weight(triangles, edges_post)

    me_pre = mean_edge_weight(edges_pre)
    me_post = mean_edge_weight(edges_post)

    weak = weak_triangles(triangles, edges_pre)
    weak_pre = triangle_total_weight(weak, edges_pre)
    weak_post = triangle_total_weight(weak, edges_post)

    inv_pre = triangle_inv_weight(triangles, edges_pre)
    inv_post = triangle_inv_weight(triangles, edges_post)

    return {
        "region": region_label,
        "node_count": len(ents),
        "edge_count": len(edges_pre),
        "triangle_count": len(triangles),
        "weak_triangle_count": len(weak),
        "E": conflict_mass_E(runs_in_region, oriented=False),
        "E_oriented": conflict_mass_E(runs_in_region, oriented=True),
        "r": graph_radius(ents, edges_pre),
        "orientation_score": orientation_score(runs_in_region),
        # Legacy (homogeneity / CV — scale-invariant)
        "triangle_homogeneity_pre": th_pre,
        "triangle_homogeneity_post": th_post,
        "delta": th_post - th_pre,  # kept name 'delta' for backward compat
        # v52.2 scale-sensitive measurements
        "triangle_total_weight_pre": tw_pre,
        "triangle_total_weight_post": tw_post,
        "delta_total_weight": tw_post - tw_pre,
        "delta_pct_total": safe_pct_change(tw_post, tw_pre),
        "mean_edge_weight_pre": me_pre,
        "mean_edge_weight_post": me_post,
        "delta_mean_edge": me_post - me_pre,
        "triangle_total_weak_pre": weak_pre,
        "triangle_total_weak_post": weak_post,
        "delta_total_weak": weak_post - weak_pre,
        "delta_pct_total_weak": safe_pct_change(weak_post, weak_pre),
        "triangle_inv_weight_pre": inv_pre,
        "triangle_inv_weight_post": inv_post,
        "delta_inv_weight": inv_post - inv_pre,
    }
