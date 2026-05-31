#!/usr/bin/env python
"""
ClarityOS engine cohort — v1.0.0-rc1 end-to-end smoke harness (Card 12.3 #8).

Drives the full operator-intelligence pipeline once, end to end, and asserts it
runs without crashing, exposes every documented field, and is deterministic
(identical inputs -> identical output). This is a verification harness, not a
unit test; the authoritative correctness gate remains ``pytest tests/`` (8768).

The operator endpoints are plain functions, so the harness calls them directly
(no HTTP layer / TestClient dependency).

Run:  python release/smoke_v1.0.0-rc1.py
Exit: 0 on success; non-zero (assertion) on any failure.

Pure verification — no operator_state writes, no wall-clock-dependent assertions
(timestamps are supplied), no new logic.
"""
import os
import sys

# Make the harness runnable from anywhere: put the repo root (parent of
# release/) on the import path so the flat phase modules resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")  # in-memory telemetry store

import phase7_storage
import phase7_telemetry
import phase9_ingest
from phase6_pipeline import run_superstructure
from phase7_endpoint import OPERATOR_ID, operator_action, operator_telemetry
from phase8_structures import build_graph, make_node
from phase8_propagation import compute_node_centrality, propagate_influence
from phase9_behavioral_motifs import analyze_behavioral_motifs
from phase9_integration import (
    SYSTEM_VARIABLE_IDS,
    action_event_to_causal_node,
    integrate_action_node,
    link_action_to_variables,
)
from phase10_forecast import compute_behavioral_forecast
from phase10_deltas import compute_behavioral_deltas
from phase10_stability import compute_behavioral_stability
from phase10_narrative import compute_behavioral_narrative
from phase11_recommendations import compute_action_recommendations
from phase11_narrative import compute_recommendation_narrative


def _ok(label):
    print(f"  [PASS] {label}")


def main() -> int:
    phase7_storage.reset()
    phase9_ingest._reset_for_tests()

    # --- Phases 1-2: runtime + telemetry -----------------------------------
    for i in range(6):
        meta = {"load": str(0.5 + 0.05 * i), "drift": str(0.1 * i), "clarity": "0.8"}
        phase7_telemetry.record_snapshot(OPERATOR_ID, run_superstructure(meta), float(i))
    history = phase7_telemetry.get_history(OPERATOR_ID, limit=100)
    assert len(history) == 6, "telemetry history not recorded"
    _ok("Phase 1-2  runtime + telemetry  (6 snapshots recorded)")

    # --- Phase 3: continuity (action ingest) -------------------------------
    for i, label in enumerate(["prune", "edit", "prune", "edit", "prune"]):
        res = operator_action({"id": f"a{i}", "label": label,
                               "timestamp": float(i + 1), "magnitude": 0.5})
        assert res.get("status") == "ok", f"action ingest failed: {res}"
    actions = phase9_ingest.get_action_continuity().get("actions", [])
    assert len(actions) == 5, "continuity log not populated"
    _ok("Phase 3    continuity  (5 actions ingested, append-only)")

    # --- Phases 5-9 via the surfacing endpoint (temporal + causal + behavioral)
    body1 = operator_telemetry()
    expected_keys = {
        "history", "latest", "analytics", "alerts", "causal_factors", "narrative",
        "causal_graph", "primary_chain", "causal_influence", "causal_centrality",
        "ranked_explanations", "causal_motifs", "causal_chains", "causal_deltas",
        "causal_stability", "causal_narrative", "unified_narrative", "behavioral_motifs",
    }
    assert expected_keys.issubset(body1.keys()), f"missing keys: {expected_keys - set(body1)}"
    assert body1["analytics"]["trajectory"] in {"Stable", "Recovering", "Wobbling", "Diverging"}
    assert body1["behavioral_motifs"]["action_loops"] == [["edit", "prune"]], "behavioral loop not detected"
    _ok("Phase 5-7  temporal engine + intelligence  (analytics / alerts / narrative)")
    _ok("Phase 8    causal engine  (graph / motifs / chains / deltas / stability / narratives)")
    _ok("Phase 9    behavioral motifs  (loop edit->prune detected)")

    # determinism: the read-only endpoint must be byte-stable
    assert operator_telemetry() == body1, "telemetry endpoint non-deterministic"
    _ok("Determinism  /operator/telemetry identical across two calls")

    # --- Phases 10-11: forecasting + recommendations (self-contained graph) -
    # Behavioral graph = the system-variable registry + the integrated action
    # nodes (mirrors the endpoint's action-augmented graph build).
    graph = build_graph([make_node(vid, "drift", vid) for vid in SYSTEM_VARIABLE_IDS], [])
    for event in sorted(actions, key=lambda e: (e.timestamp, e.id)):
        node = action_event_to_causal_node(event)
        integrate_action_node(node, graph)
        link_action_to_variables(node, graph)
    influence = propagate_influence(graph)
    centrality = compute_node_centrality(graph, influence)
    motifs = analyze_behavioral_motifs(actions, graph, influence, centrality)
    assert motifs["action_loops"] == [["edit", "prune"]], "motif loop mismatch"

    def run_10_11():
        forecast = compute_behavioral_forecast(actions, motifs, graph, influence)
        deltas = compute_behavioral_deltas(actions, [], centrality, 3.0)
        stability = compute_behavioral_stability(deltas, motifs, forecast)
        narrative = compute_behavioral_narrative(deltas, motifs, forecast, stability)
        recs = compute_action_recommendations(deltas, motifs, stability, forecast)
        rec_narr = compute_recommendation_narrative(recs, deltas, motifs, stability)
        return forecast, deltas, stability, narrative, recs, rec_narr

    forecast, deltas, stability, narrative, recs, rec_narr = run_10_11()
    assert set(forecast) == {"next_actions", "habit_trajectory", "trigger_likelihood", "loop_continuation"}
    assert set(deltas) == {"frequency", "spacing", "influence", "centrality"}
    assert set(stability) == {"score", "drivers"} and 0.0 <= stability["score"] <= 1.0
    assert set(narrative) >= {"summary", "habit_changes", "stability", "forecast_highlights"}
    assert isinstance(recs, list) and len(recs) <= 10
    assert set(rec_narr) == {"summary", "recommendations", "drivers", "stability_context", "raw"}
    _ok("Phase 10   behavioral forecast + deltas + stability + narrative")
    _ok("Phase 11   recommendations + recommendation narrative")

    assert run_10_11() == (forecast, deltas, stability, narrative, recs, rec_narr), \
        "phase 10-11 engines non-deterministic"
    _ok("Determinism  phase 10-11 engines identical across two calls")

    print("\nSMOKE OK — v1.0.0-rc1 end-to-end pipeline stable + deterministic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
