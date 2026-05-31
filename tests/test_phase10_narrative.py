# tests/test_phase10_narrative.py
#
# CARD 10.3 — Unified Behavioral Narrative: deterministic summary + habit /
# trigger / loop sections + embedded stability + forecast highlights + raw
# passthrough, from the 10.0 forecast / 10.1 deltas / 10.2 stability / 9.4 motifs.
#
# Pure / deterministic — no storage, no client, no wall-clock, no inference.
import inspect
import json

import pytest

from phase10_narrative import compute_behavioral_narrative


# ---------------------------------------------------------------------------
# Summary (deterministic, stability-driven)
# ---------------------------------------------------------------------------

def test_summary_stable():
    n = compute_behavioral_narrative({}, {}, {}, {"score": 0.85, "drivers": {}})
    assert n["summary"].startswith("Behavioral patterns are stable.")


def test_summary_shifting():
    n = compute_behavioral_narrative({}, {}, {}, {"score": 0.30, "drivers": {}})
    assert n["summary"].startswith("Behavioral patterns are shifting.")


def test_summary_moderate_includes_boundaries():
    for score in (0.5, 0.7, 0.4):           # 0.7 and 0.4 are "otherwise" → moderate
        n = compute_behavioral_narrative({}, {}, {}, {"score": score, "drivers": {}})
        assert n["summary"].startswith("Behavioral patterns show moderate change.")


def test_summary_counts_and_forecast_sentence():
    forecast = {
        "next_actions": [{"action_id": "a", "label": "A", "score": 0.42, "drivers": ["loop"]}],
        "habit_trajectory": [{"action_id": "a", "trend": "strengthening"}],
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.5}],
        "loop_continuation": [{"loop": ["a", "b"], "continuation_probability": 0.9}],
    }
    n = compute_behavioral_narrative({}, {}, forecast, {"score": 0.85, "drivers": {}})
    s = n["summary"]
    assert "1 habit change," in s          # singular
    assert "1 trigger change," in s
    assert "1 loop." in s
    assert "Top predicted next action: a (score 0.42)." in s


def test_summary_no_psychological_or_speculative_language():
    blocklist = ["anxious", "compulsive", "obsessive", "stressed", "feel",
                 "emotion", "wants", "intends", "probably", "maybe", "likely"]
    for score in (0.9, 0.5, 0.2):
        summary = compute_behavioral_narrative({}, {}, {}, {"score": score}).get("summary", "").lower()
        for word in blocklist:
            assert word not in summary


# ---------------------------------------------------------------------------
# Habit changes (trajectory + frequency delta join, sorted by |delta|)
# ---------------------------------------------------------------------------

def test_habit_changes_join_and_sort():
    deltas = {"frequency": {
        "prune": {"current": 3, "previous": 1, "delta": 0.8},
        "edit": {"current": 1, "previous": 2, "delta": -0.3},
    }}
    forecast = {"habit_trajectory": [
        {"action_id": "edit", "trend": "weakening"},
        {"action_id": "prune", "trend": "strengthening"},
    ]}
    hc = compute_behavioral_narrative(deltas, {}, forecast, {})["habit_changes"]
    assert [e["action_id"] for e in hc] == ["prune", "edit"]   # |0.8| before |0.3|
    assert hc[0]["trend"] == "strengthening"
    assert hc[0]["delta"] == pytest.approx(0.8)
    assert hc[1]["trend"] == "weakening"
    assert hc[1]["delta"] == pytest.approx(-0.3)


def test_habit_changes_delta_defaults_zero_when_unmatched():
    # trajectory action_id ("h2") not present in the (label-keyed) frequency
    # deltas → trend preserved, delta 0.0 (the documented join behaviour).
    forecast = {"habit_trajectory": [{"action_id": "h2", "trend": "stable"}]}
    hc = compute_behavioral_narrative({"frequency": {"prune": {"delta": 0.5}}}, {}, forecast, {})["habit_changes"]
    assert hc[0]["action_id"] == "h2"
    assert hc[0]["trend"] == "stable"
    assert hc[0]["delta"] == 0.0


# ---------------------------------------------------------------------------
# Trigger changes (likelihood as change signal, sorted by |delta|)
# ---------------------------------------------------------------------------

def test_trigger_changes_from_likelihood_sorted():
    forecast = {"trigger_likelihood": [
        {"chain": ["a", "f", "b"], "likelihood": 0.3},
        {"chain": ["c", "f", "d"], "likelihood": 0.9},
    ]}
    tc = compute_behavioral_narrative({}, {}, forecast, {})["trigger_changes"]
    assert tc[0]["chain"] == ["c", "f", "d"]
    assert tc[0]["delta"] == pytest.approx(0.9)
    assert tc[1]["chain"] == ["a", "f", "b"]
    assert tc[1]["delta"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Loop changes (continuation probabilities, descending)
# ---------------------------------------------------------------------------

def test_loop_changes_sorted_desc():
    forecast = {"loop_continuation": [
        {"loop": ["a", "b"], "continuation_probability": 0.4},
        {"loop": ["c", "d"], "continuation_probability": 0.9},
    ]}
    lc = compute_behavioral_narrative({}, {}, forecast, {})["loop_changes"]
    assert [e["continuation_probability"] for e in lc] == [0.9, 0.4]
    assert lc[0]["loop"] == ["c", "d"]


# ---------------------------------------------------------------------------
# Stability embedding
# ---------------------------------------------------------------------------

def test_stability_embedded():
    stability = {"score": 0.62, "drivers": {
        "habit_stability": 0.8, "trigger_stability": 0.5,
        "loop_persistence": 0.4, "action_variance": 0.7,
    }}
    embedded = compute_behavioral_narrative({}, {}, {}, stability)["stability"]
    assert embedded["score"] == pytest.approx(0.62)
    assert embedded["drivers"]["habit_stability"] == pytest.approx(0.8)
    assert embedded["drivers"]["action_variance"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Forecast highlights (top 3, projected to action_id / score / drivers)
# ---------------------------------------------------------------------------

def test_forecast_highlights_top_3_and_projection():
    forecast = {"next_actions": [
        {"action_id": "a", "label": "A", "score": 0.9, "drivers": ["loop"]},
        {"action_id": "b", "label": "B", "score": 0.7, "drivers": ["habit"]},
        {"action_id": "c", "label": "C", "score": 0.5, "drivers": ["trigger"]},
        {"action_id": "d", "label": "D", "score": 0.3, "drivers": []},
    ]}
    fh = compute_behavioral_narrative({}, {}, forecast, {})["forecast_highlights"]
    assert len(fh) == 3
    assert [e["action_id"] for e in fh] == ["a", "b", "c"]
    assert set(fh[0].keys()) == {"action_id", "score", "drivers"}   # label dropped
    assert fh[0]["drivers"] == ["loop"]
    assert fh[0]["score"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Shape, raw passthrough, empties, determinism
# ---------------------------------------------------------------------------

def test_shape_and_json():
    n = compute_behavioral_narrative({}, {}, {}, {})
    assert set(n.keys()) == {
        "summary", "habit_changes", "trigger_changes", "loop_changes",
        "stability", "forecast_highlights", "raw",
    }
    assert set(n["raw"].keys()) == {"deltas", "motifs", "forecast"}
    json.dumps(n)


def test_raw_passthrough():
    deltas = {"frequency": {"x": {"delta": 0.1}}}
    motifs = {"habits": ["x"]}
    forecast = {"next_actions": []}
    n = compute_behavioral_narrative(deltas, motifs, forecast, {})
    assert n["raw"]["deltas"] == deltas
    assert n["raw"]["motifs"] == motifs
    assert n["raw"]["forecast"] == forecast


def test_empty_inputs():
    n = compute_behavioral_narrative({}, {}, {}, {})
    assert n["habit_changes"] == []
    assert n["trigger_changes"] == []
    assert n["loop_changes"] == []
    assert n["forecast_highlights"] == []
    assert n["stability"] == {"score": 0.0, "drivers": {}}
    assert n["summary"].startswith("Behavioral patterns are shifting.")   # score 0.0 < 0.4
    assert "0 habit changes" in n["summary"]                              # plural


def test_none_inputs_safe():
    n = compute_behavioral_narrative(None, None, None, None)
    assert n["habit_changes"] == []
    assert n["summary"].startswith("Behavioral patterns are shifting.")


def test_deterministic():
    deltas = {"frequency": {"prune": {"delta": 0.8}}}
    forecast = {
        "habit_trajectory": [{"action_id": "prune", "trend": "strengthening"}],
        "next_actions": [{"action_id": "prune", "label": "P", "score": 0.5, "drivers": ["habit"]}],
        "trigger_likelihood": [],
        "loop_continuation": [],
    }
    stability = {"score": 0.6, "drivers": {"habit_stability": 0.7}}
    a = compute_behavioral_narrative(deltas, {"habits": ["prune"]}, forecast, stability)
    b = compute_behavioral_narrative(deltas, {"habits": ["prune"]}, forecast, stability)
    assert a == b


def test_no_randomness_or_wallclock():
    src = inspect.getsource(__import__("phase10_narrative"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
