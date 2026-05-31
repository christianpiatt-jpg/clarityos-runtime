# tests/test_phase11_recommendations.py
#
# CARD 11.0 — Action Recommendation Engine: the six deterministic structural
# recommendation types (habit_weakening / trigger_volatility / loop_break /
# bottleneck_relief / attractor_alignment / forecast_alignment), dedupe, and the
# top-10 descending-score list.
#
# Pure / deterministic — no storage, no client, no wall-clock, no inference.
import inspect
import json

import pytest

from phase11_recommendations import compute_action_recommendations


# ---------------------------------------------------------------------------
# Individual recommendation types
# ---------------------------------------------------------------------------

def test_habit_weakening():
    deltas = {"frequency": {
        "prune": {"current": 1, "previous": 3, "delta": -0.5},   # weakening → rec
        "edit": {"current": 3, "previous": 1, "delta": 2.0},     # strengthening → ignored
    }}
    recs = compute_action_recommendations(deltas, {}, {}, {})
    assert len(recs) == 1
    assert recs[0]["action_id"] == "prune"
    assert recs[0]["label"] == "prune"
    assert recs[0]["reason"] == "habit_weakening"
    assert recs[0]["score"] == pytest.approx(0.5)


def test_trigger_volatility():
    forecast = {"trigger_likelihood": [
        {"chain": ["a", "f", "b"], "likelihood": 0.8},
        {"chain": ["c", "f", "d"], "likelihood": 0.3},
    ]}
    recs = compute_action_recommendations({}, {}, {}, forecast)
    assert [r["reason"] for r in recs] == ["trigger_volatility", "trigger_volatility"]
    assert recs[0]["action_id"] == "a → f → b"
    assert recs[0]["score"] == pytest.approx(0.8)
    assert recs[1]["score"] == pytest.approx(0.3)


def test_loop_break():
    forecast = {"loop_continuation": [
        {"loop": ["a", "b"], "continuation_probability": 0.2},   # breakable → 0.8
        {"loop": ["c", "d"], "continuation_probability": 1.0},   # persistent → 0.0 → dropped
    ]}
    recs = compute_action_recommendations({}, {}, {}, forecast)
    assert len(recs) == 1
    assert recs[0]["reason"] == "loop_break"
    assert recs[0]["action_id"] == "a → b"
    assert recs[0]["score"] == pytest.approx(0.8)


def test_bottleneck_relief_normalized_rank():
    motifs = {"action_bottlenecks": ["act_hub", "act_2", "act_3"]}
    recs = compute_action_recommendations({}, motifs, {}, {})
    assert [r["reason"] for r in recs] == ["bottleneck_relief"] * 3
    assert recs[0]["action_id"] == "act_hub"
    assert recs[0]["score"] == pytest.approx(1.0)        # (3-0)/3
    assert recs[1]["score"] == pytest.approx(2 / 3)      # (3-1)/3
    assert recs[2]["score"] == pytest.approx(1 / 3)      # (3-2)/3


def test_attractor_alignment_normalized_rank():
    motifs = {"action_attractors": ["act_sink", "act_2"]}
    recs = compute_action_recommendations({}, motifs, {}, {})
    assert [r["reason"] for r in recs] == ["attractor_alignment"] * 2
    assert recs[0]["action_id"] == "act_sink"
    assert recs[0]["score"] == pytest.approx(1.0)        # (2-0)/2
    assert recs[1]["score"] == pytest.approx(0.5)        # (2-1)/2


def test_forecast_alignment_keyed_by_label():
    forecast = {"next_actions": [
        {"action_id": "e2", "label": "edit", "score": 0.9, "drivers": ["loop"]},
        {"action_id": "p0", "label": "prune", "score": 0.4, "drivers": ["habit"]},
    ]}
    recs = compute_action_recommendations({}, {}, {}, forecast)
    assert recs[0]["reason"] == "forecast_alignment"
    assert recs[0]["action_id"] == "edit"      # label, not the event-id "e2"
    assert recs[0]["label"] == "edit"
    assert recs[0]["score"] == pytest.approx(0.9)
    assert recs[1]["action_id"] == "prune"


# ---------------------------------------------------------------------------
# Dedupe, ordering, top-10, combined
# ---------------------------------------------------------------------------

def test_dedupe_keeps_highest_scoring_reason():
    # "edit" is both a weakening habit (0.3) and a strong forecast (0.9).
    deltas = {"frequency": {"edit": {"current": 2, "previous": 3, "delta": -0.3}}}
    forecast = {"next_actions": [{"action_id": "e2", "label": "edit", "score": 0.9, "drivers": []}]}
    recs = compute_action_recommendations(deltas, {}, {}, forecast)
    edit_recs = [r for r in recs if r["action_id"] == "edit"]
    assert len(edit_recs) == 1                      # deduped
    assert edit_recs[0]["reason"] == "forecast_alignment"
    assert edit_recs[0]["score"] == pytest.approx(0.9)


def test_sorted_desc_and_top_10_cap():
    deltas = {"frequency": {f"a{i:02d}": {"delta": -(i + 1) / 100} for i in range(12)}}
    recs = compute_action_recommendations(deltas, {}, {}, {})
    assert len(recs) == 10                          # 12 candidates capped to 10
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)   # descending
    assert recs[0]["score"] == pytest.approx(0.12)  # strongest weakening (a11)
    assert all(r["score"] >= 0.03 - 1e-9 for r in recs)   # weakest two dropped


def test_all_six_reason_types_present_and_sorted():
    deltas = {"frequency": {"prune": {"delta": -0.55}}}
    motifs = {"action_bottlenecks": ["b1"], "action_attractors": ["a1"]}
    forecast = {
        "next_actions": [{"action_id": "e2", "label": "edit", "score": 0.95, "drivers": []}],
        "trigger_likelihood": [{"chain": ["x", "f", "y"], "likelihood": 0.7}],
        "loop_continuation": [{"loop": ["m", "n"], "continuation_probability": 0.25}],
    }
    recs = compute_action_recommendations(deltas, motifs, {"score": 0.5}, forecast)
    assert {r["reason"] for r in recs} == {
        "habit_weakening", "trigger_volatility", "loop_break",
        "bottleneck_relief", "attractor_alignment", "forecast_alignment",
    }
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    for r in recs:
        assert 0.0 < r["score"] <= 1.0


# ---------------------------------------------------------------------------
# Shape, empties, determinism, structural guards
# ---------------------------------------------------------------------------

def test_shape_and_json():
    forecast = {"next_actions": [{"action_id": "e2", "label": "edit", "score": 0.9, "drivers": ["loop"]}]}
    recs = compute_action_recommendations({}, {}, {}, forecast)
    assert set(recs[0].keys()) == {"action_id", "label", "reason", "score"}
    json.dumps(recs)


def test_empty_inputs():
    assert compute_action_recommendations({}, {}, {}, {}) == []


def test_none_inputs_safe():
    assert compute_action_recommendations(None, None, None, None) == []


def test_zero_score_candidates_dropped():
    # likelihood 0 (trigger) and continuation 1.0 (loop) both yield score 0.
    forecast = {
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.0}],
        "loop_continuation": [{"loop": ["c", "d"], "continuation_probability": 1.0}],
    }
    assert compute_action_recommendations({}, {}, {}, forecast) == []


def test_deterministic():
    deltas = {"frequency": {"prune": {"delta": -0.5}}}
    motifs = {"action_bottlenecks": ["h1", "h2"], "action_attractors": ["s1"]}
    forecast = {
        "next_actions": [{"action_id": "e2", "label": "edit", "score": 0.9, "drivers": []}],
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.6}],
        "loop_continuation": [{"loop": ["x", "y"], "continuation_probability": 0.1}],
    }
    a = compute_action_recommendations(deltas, motifs, {"score": 0.5}, forecast)
    b = compute_action_recommendations(deltas, motifs, {"score": 0.5}, forecast)
    assert a == b


def test_no_randomness_or_wallclock():
    src = inspect.getsource(__import__("phase11_recommendations"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
