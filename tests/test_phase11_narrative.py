# tests/test_phase11_narrative.py
#
# CARD 11.1 — Recommendation Narrative: deterministic summary + per-recommendation
# explanation templates + drivers partition + embedded stability + raw passthrough.
#
# Pure / deterministic — no storage, no client, no wall-clock, no inference.
import inspect
import json

import pytest

from phase11_narrative import compute_recommendation_narrative


# One 11.0-style recommendation per reason type (descending score, as 11.0 emits).
RECS = [
    {"action_id": "edit", "label": "edit", "reason": "forecast_alignment", "score": 0.9},
    {"action_id": "b1", "label": "b1", "reason": "bottleneck_relief", "score": 0.8},
    {"action_id": "prune", "label": "prune", "reason": "habit_weakening", "score": 0.5},
    {"action_id": "x → f → y", "label": "x → f → y", "reason": "trigger_volatility", "score": 0.4},
    {"action_id": "m → n", "label": "m → n", "reason": "loop_break", "score": 0.3},
    {"action_id": "a1", "label": "a1", "reason": "attractor_alignment", "score": 0.2},
]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def test_summary_stable():
    n = compute_recommendation_narrative([], {}, {}, {"score": 0.85, "drivers": {}})
    assert n["summary"].startswith("Behavioral system is stable; recommendations focus on optimization.")


def test_summary_unstable():
    n = compute_recommendation_narrative([], {}, {}, {"score": 0.30, "drivers": {}})
    assert n["summary"].startswith("Behavioral system shows instability; recommendations target stabilization.")


def test_summary_moderate_includes_boundaries():
    for score in (0.5, 0.7, 0.4):           # 0.7 / 0.4 are "otherwise" → moderate
        n = compute_recommendation_narrative([], {}, {}, {"score": score, "drivers": {}})
        assert n["summary"].startswith("Behavioral system shows moderate variability")


def test_summary_counts_and_top():
    n = compute_recommendation_narrative(RECS, {}, {}, {"score": 0.5, "drivers": {}})
    s = n["summary"]
    assert "Generated 6 recommendations across 6 reason types." in s
    assert "Top recommendation: edit — forecast_alignment (score 0.90)." in s


def test_summary_no_psychological_or_speculative_language():
    blocklist = ["anxious", "compulsive", "obsessive", "stressed", "feel",
                 "emotion", "wants", "intends", "probably", "maybe", "likely"]
    for score in (0.9, 0.5, 0.2):
        summary = compute_recommendation_narrative([], {}, {}, {"score": score}).get("summary", "").lower()
        for word in blocklist:
            assert word not in summary


# ---------------------------------------------------------------------------
# Recommendation explanations (deterministic templates)
# ---------------------------------------------------------------------------

def test_recommendation_explanations():
    explained = compute_recommendation_narrative(RECS, {}, {}, {})["recommendations"]
    by_reason = {r["reason"]: r["explanation"] for r in explained}
    assert by_reason["habit_weakening"] == "This action is recommended because its habit strength is decreasing."
    assert by_reason["trigger_volatility"] == "This action is recommended due to volatility in its associated trigger chain."
    assert by_reason["loop_break"] == "This action is recommended to interrupt a weakening or unstable loop."
    assert by_reason["bottleneck_relief"] == "This action is recommended because it is a bottleneck with high inbound influence."
    assert by_reason["attractor_alignment"] == "This action aligns with a strong behavioral attractor."
    assert by_reason["forecast_alignment"] == "This action is predicted as likely in the near future."
    assert set(explained[0].keys()) == {"action_id", "label", "reason", "score", "explanation"}


def test_recommendations_preserve_order():
    explained = compute_recommendation_narrative(RECS, {}, {}, {})["recommendations"]
    assert [r["action_id"] for r in explained] == ["edit", "b1", "prune", "x → f → y", "m → n", "a1"]


def test_unknown_reason_gets_empty_explanation():
    recs = [{"action_id": "z", "label": "z", "reason": "mystery", "score": 0.5}]
    explained = compute_recommendation_narrative(recs, {}, {}, {})["recommendations"]
    assert explained[0]["explanation"] == ""


# ---------------------------------------------------------------------------
# Drivers partition
# ---------------------------------------------------------------------------

def test_drivers_extraction():
    d = compute_recommendation_narrative(RECS, {}, {}, {})["drivers"]
    assert set(d.keys()) == {"habit", "triggers", "loops", "bottlenecks", "attractors", "forecast_alignment"}
    assert [(e["action_id"], e["reason"]) for e in d["habit"]] == [("prune", "habit_weakening")]
    assert d["habit"][0]["metric"] == pytest.approx(0.5)
    assert [(e["action_id"], e["reason"]) for e in d["triggers"]] == [("x → f → y", "trigger_volatility")]
    assert [(e["action_id"], e["reason"]) for e in d["loops"]] == [("m → n", "loop_break")]
    assert [(e["action_id"], e["reason"]) for e in d["bottlenecks"]] == [("b1", "bottleneck_relief")]
    assert [(e["action_id"], e["reason"]) for e in d["attractors"]] == [("a1", "attractor_alignment")]
    assert d["forecast_alignment"][0]["action_id"] == "edit"
    assert d["forecast_alignment"][0]["metric"] == pytest.approx(0.9)


def test_drivers_multiple_in_bucket_preserve_order():
    recs = [
        {"action_id": "a", "label": "a", "reason": "habit_weakening", "score": 0.9},
        {"action_id": "b", "label": "b", "reason": "habit_weakening", "score": 0.4},
    ]
    habit = compute_recommendation_narrative(recs, {}, {}, {})["drivers"]["habit"]
    assert [e["action_id"] for e in habit] == ["a", "b"]      # score-desc preserved


# ---------------------------------------------------------------------------
# Stability context, raw, shape, empties, determinism, guards
# ---------------------------------------------------------------------------

def test_stability_context_embedded():
    stability = {"score": 0.62, "drivers": {
        "habit_stability": 0.8, "trigger_stability": 0.5,
        "loop_persistence": 0.4, "action_variance": 0.7,
    }}
    ctx = compute_recommendation_narrative([], {}, {}, stability)["stability_context"]
    assert ctx["score"] == pytest.approx(0.62)
    assert ctx["drivers"]["habit_stability"] == pytest.approx(0.8)
    assert ctx["drivers"]["action_variance"] == pytest.approx(0.7)


def test_raw_passthrough():
    deltas = {"frequency": {"x": {"delta": -0.1}}}
    motifs = {"action_bottlenecks": ["b1"]}
    n = compute_recommendation_narrative(RECS, deltas, motifs, {})
    assert n["raw"]["recommendations"] == RECS
    assert n["raw"]["deltas"] == deltas
    assert n["raw"]["motifs"] == motifs


def test_shape_and_json():
    n = compute_recommendation_narrative(RECS, {}, {}, {"score": 0.5, "drivers": {}})
    assert set(n.keys()) == {"summary", "recommendations", "drivers", "stability_context", "raw"}
    assert set(n["raw"].keys()) == {"recommendations", "deltas", "motifs"}
    json.dumps(n)


def test_empty_inputs():
    n = compute_recommendation_narrative([], {}, {}, {})
    assert n["recommendations"] == []
    assert all(n["drivers"][bucket] == [] for bucket in n["drivers"])
    assert n["stability_context"] == {"score": 0.0, "drivers": {}}
    assert n["summary"].startswith("Behavioral system shows instability")   # score 0.0 < 0.4
    assert "0 recommendations across 0 reason types" in n["summary"]


def test_none_inputs_safe():
    n = compute_recommendation_narrative(None, None, None, None)
    assert n["recommendations"] == []
    assert n["summary"].startswith("Behavioral system shows instability")


def test_deterministic():
    a = compute_recommendation_narrative(RECS, {"frequency": {}}, {"action_bottlenecks": ["b1"]},
                                         {"score": 0.5, "drivers": {"habit_stability": 0.6}})
    b = compute_recommendation_narrative(RECS, {"frequency": {}}, {"action_bottlenecks": ["b1"]},
                                         {"score": 0.5, "drivers": {"habit_stability": 0.6}})
    assert a == b


def test_no_randomness_or_wallclock():
    src = inspect.getsource(__import__("phase11_narrative"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
