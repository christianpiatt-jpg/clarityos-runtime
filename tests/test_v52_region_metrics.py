"""v52 — unit tests for ELINS.region_metrics."""
from __future__ import annotations

import math
import os
import sys

# Ensure repo root is on sys.path for in-tree pytest runs.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ELINS import region_metrics as rm
from ELINS import forecast_engine


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _mk_run(*, region_code, entities, intensities, ts=1.0):
    return {
        "region_code": region_code,
        "_extracted_entities": list(entities),
        "primitives": {"intensities": dict(intensities)},
        "input_phase": {"ts": ts},
    }


# ---------------------------------------------------------------------------
# scalars
# ---------------------------------------------------------------------------
def test_stress_and_relief_mass_sums_correctly():
    run = _mk_run(
        region_code="US",
        entities=["A"],
        intensities={"pressure": 1.0, "tension": 0.5, "drift": 0.25,
                     "contradiction": 0.1, "alignment": 0.4, "trust": 0.3},
    )
    assert rm.stress_mass(run) == 1.0 + 0.5 + 0.25 + 0.1
    assert rm.relief_mass(run) == 0.4 + 0.3


def test_orientation_score_bounds_and_zero_division_safe():
    a = _mk_run(region_code="US", entities=["X"],
                intensities={"alignment": 1.0, "pressure": 0.0})
    assert rm.orientation_score([a]) == 1.0
    b = _mk_run(region_code="US", entities=["X"],
                intensities={"pressure": 1.0, "alignment": 0.0})
    assert rm.orientation_score([b]) == 0.0
    empty = _mk_run(region_code="US", entities=["X"], intensities={})
    assert rm.orientation_score([empty]) == 0.0


def test_envelope_integral_oriented_strictly_lower_than_default():
    run = _mk_run(
        region_code="US",
        entities=["X", "Y"],
        intensities={"pressure": 1.0, "tension": 1.0,
                     "drift": 0.5, "contradiction": 0.5},
    )
    e_def = rm.envelope_integral(run, oriented=False)
    e_ori = rm.envelope_integral(run, oriented=True)
    assert e_ori < e_def
    # Sanity: both positive, both finite
    assert e_def > 0 and math.isfinite(e_def)
    assert e_ori > 0 and math.isfinite(e_ori)


def test_envelope_integral_zero_intensities_returns_zero():
    run = _mk_run(region_code="US", entities=["X"], intensities={})
    assert rm.envelope_integral(run) == 0.0


def test_orientation_lambdas_only_bumps_stress_keys():
    out = rm.orientation_lambdas()
    base = forecast_engine.DEFAULT_LAMBDAS
    for k in rm.STRESS_PRIMS:
        assert out[k] == base[k] * (1.0 + rm.ORIENTATION_LAMBDA_BUMP)
    for k in rm.RELIEF_PRIMS:
        assert out[k] == base[k]


# ---------------------------------------------------------------------------
# graph builder
# ---------------------------------------------------------------------------
def test_envelope_weighted_graph_has_pairwise_edges():
    runs = [
        _mk_run(region_code="US", entities=["A", "B", "C"],
                intensities={"pressure": 1.0}),
    ]
    g = rm.build_envelope_weighted_graph(runs)
    # K3 over {A, B, C}
    assert set(g["entities"].keys()) == {"A", "B", "C"}
    assert len(g["edges"]) == 3
    for k in g["edges"]:
        assert "||" in k


def test_envelope_weighted_graph_oriented_lower_edge_weight():
    runs = [
        _mk_run(region_code="US", entities=["A", "B"],
                intensities={"pressure": 1.0}),
    ]
    g_def = rm.build_envelope_weighted_graph(runs, oriented=False)
    g_ori = rm.build_envelope_weighted_graph(runs, oriented=True)
    assert g_def["edges"]["A||B"]["weight"] > g_ori["edges"]["A||B"]["weight"]


def test_induced_subgraph_filters_by_cluster():
    runs = [
        _mk_run(region_code="US", entities=["A", "B"],
                intensities={"pressure": 0.5}),
        _mk_run(region_code="EU", entities=["C", "D"],
                intensities={"tension": 0.5}),
    ]
    g = rm.build_envelope_weighted_graph(runs)
    ents_us, edges_us = rm.induced_subgraph(g, "US")
    assert ents_us == {"A", "B"}
    assert len(edges_us) == 1
    ents_eu, _ = rm.induced_subgraph(g, "EU")
    assert ents_eu == {"C", "D"}


# ---------------------------------------------------------------------------
# topology
# ---------------------------------------------------------------------------
def test_graph_radius_singleton_and_K3():
    ents = {"A"}
    edges = {}
    assert rm.graph_radius(ents, edges) == 1

    # Path A — B — C  has eccentricity 2 from endpoints
    ents = {"A", "B", "C"}
    edges = {
        "A||B": {"a": "A", "b": "B", "weight": 1.0},
        "B||C": {"a": "B", "b": "C", "weight": 1.0},
    }
    assert rm.graph_radius(ents, edges) == 2

    # K3 has eccentricity 1 everywhere
    edges_k3 = dict(edges)
    edges_k3["A||C"] = {"a": "A", "b": "C", "weight": 1.0}
    assert rm.graph_radius(ents, edges_k3) == 1


def test_find_triangles_K4_yields_4_triangles():
    ents = {"A", "B", "C", "D"}
    pairs = [("A", "B"), ("A", "C"), ("A", "D"),
             ("B", "C"), ("B", "D"), ("C", "D")]
    edges = {f"{a}||{b}": {"a": a, "b": b, "weight": 1.0} for a, b in pairs}
    triangles = rm.find_triangles(ents, edges)
    assert len(triangles) == 4   # C(4,3)


def test_triangle_homogeneity_equilateral_one():
    ents = {"A", "B", "C"}
    edges = {
        "A||B": {"a": "A", "b": "B", "weight": 1.0},
        "A||C": {"a": "A", "b": "C", "weight": 1.0},
        "B||C": {"a": "B", "b": "C", "weight": 1.0},
    }
    triangles = rm.find_triangles(ents, edges)
    assert rm.triangle_homogeneity(triangles, edges) == 1.0


def test_triangle_homogeneity_skewed_below_one():
    ents = {"A", "B", "C"}
    edges = {
        "A||B": {"a": "A", "b": "B", "weight": 10.0},
        "A||C": {"a": "A", "b": "C", "weight": 1.0},
        "B||C": {"a": "B", "b": "C", "weight": 1.0},
    }
    triangles = rm.find_triangles(ents, edges)
    h = rm.triangle_homogeneity(triangles, edges)
    assert 0.0 <= h < 1.0


def test_triangle_homogeneity_zero_when_no_triangles():
    ents = {"A", "B"}
    edges = {"A||B": {"a": "A", "b": "B", "weight": 1.0}}
    assert rm.triangle_homogeneity([], edges) == 0.0


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------
def test_region_metrics_row_pre_post_topology_stable():
    runs = [
        _mk_run(region_code="US", entities=["A", "B", "C"],
                intensities={"pressure": 1.0, "alignment": 0.5}),
        _mk_run(region_code="US", entities=["A", "B", "D"],
                intensities={"pressure": 0.5, "tension": 0.5}),
    ]
    g_pre = rm.build_envelope_weighted_graph(runs, oriented=False)
    g_post = rm.build_envelope_weighted_graph(runs, oriented=True)
    row = rm.region_metrics_row("US", runs, g_pre, g_post)

    # Topology must match between pre and post
    assert row["node_count"] == 4
    assert row["E"] > row["E_oriented"]
    # Triangle homogeneity well-defined and bounded
    assert 0.0 <= row["triangle_homogeneity_pre"] <= 1.0
    assert 0.0 <= row["triangle_homogeneity_post"] <= 1.0


def test_region_metrics_row_orientation_reduces_E():
    runs = [
        _mk_run(region_code="MEA", entities=["Iran", "OPEC"],
                intensities={"pressure": 1.5, "tension": 1.0,
                             "drift": 0.5, "contradiction": 0.3}),
    ]
    g_pre = rm.build_envelope_weighted_graph(runs, oriented=False)
    g_post = rm.build_envelope_weighted_graph(runs, oriented=True)
    row = rm.region_metrics_row("MEA", runs, g_pre, g_post)
    assert row["E"] > row["E_oriented"] > 0


# ---------------------------------------------------------------------------
# v52.2 — scale-sensitive DV tests
# ---------------------------------------------------------------------------
def _mk_graph_K3(weight: float) -> tuple:
    """Tiny K3 fixture. Returns (entities_set, edges_dict)."""
    ents = {"A", "B", "C"}
    edges = {
        "A||B": {"a": "A", "b": "B", "weight": float(weight)},
        "A||C": {"a": "A", "b": "C", "weight": float(weight)},
        "B||C": {"a": "B", "b": "C", "weight": float(weight)},
    }
    return ents, edges


def test_new_fields_present_on_sample_row():
    runs = [
        _mk_run(region_code="US", entities=["A", "B", "C"],
                intensities={"pressure": 1.0, "tension": 0.5,
                             "alignment": 0.3}),
    ]
    g_pre = rm.build_envelope_weighted_graph(runs, oriented=False)
    g_post = rm.build_envelope_weighted_graph(runs, oriented=True)
    row = rm.region_metrics_row("US", runs, g_pre, g_post)
    expected = {
        "weak_triangle_count",
        "triangle_total_weight_pre", "triangle_total_weight_post",
        "delta_total_weight", "delta_pct_total",
        "mean_edge_weight_pre", "mean_edge_weight_post", "delta_mean_edge",
        "triangle_total_weak_pre", "triangle_total_weak_post",
        "delta_total_weak", "delta_pct_total_weak",
        "triangle_inv_weight_pre", "triangle_inv_weight_post",
        "delta_inv_weight",
    }
    missing = expected - set(row.keys())
    assert not missing, f"missing fields: {missing}"


def test_uniform_multiplicative_scaling_invariance():
    """Multiply every edge weight by 0.86 — total/pct deltas track the
    scaling exactly; homogeneity stays invariant (CV unchanged)."""
    ents, edges_pre = _mk_graph_K3(weight=10.0)
    _, edges_post = _mk_graph_K3(weight=8.6)  # 0.86 * 10.0
    triangles = rm.find_triangles(ents, edges_pre)

    # Total: pre = 30, post = 25.8 → pct = -0.14
    tw_pre = rm.triangle_total_weight(triangles, edges_pre)
    tw_post = rm.triangle_total_weight(triangles, edges_post)
    assert math.isclose(tw_pre, 30.0, abs_tol=1e-9)
    assert math.isclose(tw_post, 25.8, abs_tol=1e-9)
    pct = rm.safe_pct_change(tw_post, tw_pre)
    assert math.isclose(pct, -0.14, abs_tol=1e-6)

    # Mean edge weight: pre = 10, post = 8.6
    assert math.isclose(rm.mean_edge_weight(edges_pre), 10.0, abs_tol=1e-9)
    assert math.isclose(rm.mean_edge_weight(edges_post), 8.6, abs_tol=1e-9)

    # Homogeneity invariant under uniform scaling (all edges equal in K3
    # means CV = 0, so homogeneity = 1.0 in both states).
    th_pre = rm.triangle_homogeneity(triangles, edges_pre)
    th_post = rm.triangle_homogeneity(triangles, edges_post)
    assert math.isclose(th_pre, th_post, abs_tol=1e-9)


def test_weak_edge_only_perturbation_amplifies_weak_DV():
    """K4 with three weak edges (distinct values below q25) and three
    strong edges (distinct values above q25). Scale only the weak
    edges by 0.5 (post). Expect delta_pct_total_weak to be larger in
    magnitude than delta_pct_total."""
    # Distinct weights so the q25 threshold doesn't tie at any edge.
    edge_weights_pre = {
        "A||B": 1.0, "A||D": 1.5, "C||D": 2.0,    # weak
        "A||C": 10.0, "B||C": 10.5, "B||D": 11.0, # strong
    }
    edge_weights_post = dict(edge_weights_pre)
    # Halve only the weak edges
    for k in ("A||B", "A||D", "C||D"):
        edge_weights_post[k] = edge_weights_pre[k] * 0.5

    def _build(weights):
        out = {}
        for k, w in weights.items():
            a, b = k.split("||")
            out[k] = {"a": a, "b": b, "weight": float(w)}
        return out

    ents = {"A", "B", "C", "D"}
    edges_pre = _build(edge_weights_pre)
    edges_post = _build(edge_weights_post)
    triangles = rm.find_triangles(ents, edges_pre)

    # Pre/post overall total
    tw_pre = rm.triangle_total_weight(triangles, edges_pre)
    tw_post = rm.triangle_total_weight(triangles, edges_post)
    pct_overall = rm.safe_pct_change(tw_post, tw_pre)

    # Weak triangles identified from pre graph (threshold = 25th
    # percentile of edge weights). Reuse this set for both pre/post sums.
    weak = rm.weak_triangles(triangles, edges_pre)
    assert len(weak) >= 1
    weak_pre = rm.triangle_total_weight(weak, edges_pre)
    weak_post = rm.triangle_total_weight(weak, edges_post)
    pct_weak = rm.safe_pct_change(weak_post, weak_pre)

    # Weak DV moves substantially more than overall DV
    assert abs(pct_weak) > abs(pct_overall)
    # Both should be negative (post < pre)
    assert pct_weak < 0 and pct_overall < 0

    # Inverse-weight sum increases when weak edges get weaker
    inv_pre = rm.triangle_inv_weight(triangles, edges_pre)
    inv_post = rm.triangle_inv_weight(triangles, edges_post)
    assert inv_post > inv_pre


def test_inverse_weight_regularization_no_nan_for_zero_edges():
    """Edges with weight 0 must not produce NaN/inf in inv_weight."""
    ents, edges = _mk_graph_K3(weight=0.0)
    triangles = rm.find_triangles(ents, edges)
    inv = rm.triangle_inv_weight(triangles, edges)
    assert math.isfinite(inv) and inv > 0


def test_safe_pct_change_handles_zero_baseline():
    """Pre = 0 must not raise ZeroDivisionError or produce inf."""
    val = rm.safe_pct_change(post=1.0, pre=0.0)
    assert math.isfinite(val)
    val_neg = rm.safe_pct_change(post=-1.0, pre=0.0)
    assert math.isfinite(val_neg)


def test_quantile_basic_cases():
    assert rm.quantile([], 0.5) == 0.0
    assert rm.quantile([5.0], 0.5) == 5.0
    assert math.isclose(rm.quantile([1.0, 2.0, 3.0, 4.0], 0.25), 1.75, abs_tol=1e-9)
    assert math.isclose(rm.quantile([1.0, 2.0, 3.0, 4.0], 0.5), 2.5, abs_tol=1e-9)
