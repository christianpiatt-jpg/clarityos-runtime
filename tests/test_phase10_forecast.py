# tests/test_phase10_forecast.py
#
# CARD 10.0 — Behavioral Forecast Engine: next-action prediction, habit
# trajectory, trigger likelihood, loop continuation, and the unified forecast.
#
# Pure / deterministic — no storage, no client, no wall-clock. Mirrors the 9.4
# motif test style (hand-built ActionEvents + motif dicts).
import inspect
import json

import pytest

from phase8_structures import build_graph, make_node
from phase9_actions import ActionEvent
from phase10_forecast import (
    HABIT_WEIGHT,
    LOOP_WEIGHT,
    compute_behavioral_forecast,
    forecast_habit_trajectory,
    forecast_loop_continuation,
    forecast_next_actions,
    forecast_trigger_likelihood,
)


def _ev(id, label, ts, mag=None):
    return ActionEvent(id=id, label=label, timestamp=ts, magnitude=mag)


EMPTY_MOTIFS = {
    "action_loops": [],
    "trigger_chains": [],
    "habits": [],
    "action_bottlenecks": [],
    "action_attractors": [],
}


def _motifs(**overrides):
    return {**EMPTY_MOTIFS, **overrides}


# ---------------------------------------------------------------------------
# forecast_next_actions — loop / habit / trigger / influence scoring
# ---------------------------------------------------------------------------

def test_next_actions_loop_prediction():
    # prune -> edit -> prune (last = prune); loop ["edit", "prune"] → next "edit".
    actions = [_ev("1", "prune", 1.0), _ev("2", "edit", 2.0), _ev("3", "prune", 3.0)]
    motifs = _motifs(action_loops=[["edit", "prune"]])
    result = forecast_next_actions(actions, motifs, build_graph([], []), {})
    top = result[0]
    assert top["label"] == "edit"
    assert top["drivers"] == ["loop"]
    assert top["score"] == pytest.approx(LOOP_WEIGHT)        # 0.4
    assert top["action_id"] == "2"                           # latest "edit" event id


def test_next_actions_weighted_score_all_drivers():
    # "edit" is the loop successor, a habit, a trigger endpoint, and the most
    # influential → score 0.4 + 0.3 + 0.2 + 0.1 = 1.0 with all three drivers.
    actions = [
        _ev("e0", "edit", 10.0, 0.5), _ev("e1", "edit", 20.0, 0.5),
        _ev("e2", "edit", 30.0, 0.5), _ev("p0", "prune", 40.0, 0.0),
    ]
    motifs = _motifs(
        action_loops=[["edit", "prune"]],
        habits=["edit"],
        trigger_chains=[["e0", "factor_0", "p0"]],
    )
    influence = {"e2": 0.5}
    result = forecast_next_actions(actions, motifs, build_graph([], []), influence)
    top = result[0]
    assert top["label"] == "edit"
    assert top["score"] == pytest.approx(1.0)
    assert top["drivers"] == ["loop", "habit", "trigger"]
    assert top["action_id"] == "e2"


def test_next_actions_habit_frequency_normalized():
    actions = [_ev(f"a{i}", "a", float(10 * i)) for i in range(4)]            # freq 4
    actions += [_ev(f"b{i}", "b", float(100 + 10 * i)) for i in range(3)]     # freq 3
    motifs = _motifs(habits=["a", "b"])
    result = forecast_next_actions(actions, motifs, build_graph([], []), {})
    by_label = {r["label"]: r for r in result}
    assert by_label["a"]["score"] == pytest.approx(HABIT_WEIGHT * 1.0)        # 0.30
    assert by_label["b"]["score"] == pytest.approx(HABIT_WEIGHT * (3 / 4))    # 0.225
    assert by_label["a"]["drivers"] == ["habit"]
    assert result[0]["label"] == "a"                                          # higher first


def test_next_actions_empty_without_signal():
    # Actions but no motifs and no influence → every score is 0 → no prediction.
    actions = [_ev("1", "a", 1.0), _ev("2", "b", 2.0)]
    assert forecast_next_actions(actions, EMPTY_MOTIFS, build_graph([], []), {}) == []


def test_next_actions_empty_for_no_actions():
    assert forecast_next_actions([], EMPTY_MOTIFS, build_graph([], []), {}) == []


def test_next_actions_capped_at_top_5():
    labels = ["a", "b", "c", "d", "e", "f"]                  # freq 6,5,4,3,2,1
    actions = []
    for j, label in enumerate(labels):
        for i in range(6 - j):
            actions.append(_ev(f"{label}{i}", label, float(j * 100 + 10 * i)))
    result = forecast_next_actions(actions, _motifs(habits=labels), build_graph([], []), {})
    assert len(result) == 5
    assert [r["label"] for r in result] == ["a", "b", "c", "d", "e"]   # freq desc


# ---------------------------------------------------------------------------
# forecast_habit_trajectory — strengthening / weakening / stable
# ---------------------------------------------------------------------------

def test_habit_trajectory_strengthening():
    # gaps tighten: 10, 10 → 2, 2
    actions = [_ev(f"s{i}", "sync", t) for i, t in enumerate([0.0, 10.0, 20.0, 22.0, 24.0])]
    [traj] = forecast_habit_trajectory(actions)
    assert traj["trend"] == "strengthening"
    assert traj["action_id"] == "s4"                         # latest event id


def test_habit_trajectory_weakening():
    # gaps loosen: 2, 2 → 10, 10
    actions = [_ev(f"s{i}", "sync", t) for i, t in enumerate([0.0, 2.0, 4.0, 14.0, 24.0])]
    [traj] = forecast_habit_trajectory(actions)
    assert traj["trend"] == "weakening"


def test_habit_trajectory_stable():
    # even spacing → no change
    actions = [_ev(f"s{i}", "sync", t) for i, t in enumerate([0.0, 10.0, 20.0, 30.0])]
    [traj] = forecast_habit_trajectory(actions)
    assert traj["trend"] == "stable"


def test_habit_trajectory_ignores_below_min_recurrence():
    assert forecast_habit_trajectory([_ev("1", "sync", 0.0), _ev("2", "sync", 10.0)]) == []


def test_habit_trajectory_sorted_by_label():
    actions = []
    for label in ("zebra", "alpha"):
        actions += [_ev(f"{label}{i}", label, float(10 * i)) for i in range(3)]
    trends = forecast_habit_trajectory(actions)
    # representative ids are alpha2 / zebra2; output ordered by label.
    assert [t["action_id"] for t in trends] == ["alpha2", "zebra2"]


# ---------------------------------------------------------------------------
# forecast_trigger_likelihood
# ---------------------------------------------------------------------------

def test_trigger_likelihood_normalized_and_ranked():
    motifs = _motifs(trigger_chains=[
        ["act_a", "factor_0", "act_b"],     # raw 0.8 + 0.2 = 1.0  (max)
        ["act_c", "factor_1", "act_d"],     # raw 0.1 + 0.1 = 0.2
    ])
    influence = {"act_a": 0.8, "factor_0": 0.2, "act_c": 0.1, "factor_1": 0.1}
    result = forecast_trigger_likelihood(motifs, influence)
    assert result[0]["chain"] == ["act_a", "factor_0", "act_b"]
    assert result[0]["likelihood"] == pytest.approx(1.0)
    assert result[1]["chain"] == ["act_c", "factor_1", "act_d"]
    assert result[1]["likelihood"] == pytest.approx(0.2)


def test_trigger_likelihood_empty_without_chains():
    assert forecast_trigger_likelihood(EMPTY_MOTIFS, {"x": 0.5}) == []


def test_trigger_likelihood_zero_influence():
    motifs = _motifs(trigger_chains=[["act_a", "factor_0", "act_b"]])
    [res] = forecast_trigger_likelihood(motifs, {})
    assert res["likelihood"] == 0.0                          # no influence → 0


# ---------------------------------------------------------------------------
# forecast_loop_continuation
# ---------------------------------------------------------------------------

def test_loop_continuation_active_loop_is_one():
    labels = ["prune", "edit", "prune", "edit", "prune", "edit"]
    actions = [_ev(str(i), lbl, float(10 * i)) for i, lbl in enumerate(labels)]
    [res] = forecast_loop_continuation(_motifs(action_loops=[["edit", "prune"]]), actions)
    assert res["loop"] == ["edit", "prune"]
    assert res["continuation_probability"] == pytest.approx(1.0)


def test_loop_continuation_abandoned_loop_is_lower():
    # cycled, then abandoned for an unrelated action → recency drags it down.
    labels = ["prune", "edit", "prune", "edit", "save", "save", "save"]
    actions = [_ev(str(i), lbl, float(10 * i)) for i, lbl in enumerate(labels)]
    [res] = forecast_loop_continuation(_motifs(action_loops=[["edit", "prune"]]), actions)
    assert 0.0 <= res["continuation_probability"] < 1.0


def test_loop_continuation_ranked_desc():
    labels = ["a", "b", "a", "b", "c", "d"]
    actions = [_ev(str(i), lbl, float(10 * i)) for i, lbl in enumerate(labels)]
    motifs = _motifs(action_loops=[["a", "b"], ["c", "d"]])
    probs = [r["continuation_probability"] for r in forecast_loop_continuation(motifs, actions)]
    assert probs == sorted(probs, reverse=True)


def test_loop_continuation_in_unit_range():
    labels = ["a", "b", "a", "b", "a"]
    actions = [_ev(str(i), lbl, float(10 * i)) for i, lbl in enumerate(labels)]
    for res in forecast_loop_continuation(_motifs(action_loops=[["a", "b"]]), actions):
        assert 0.0 <= res["continuation_probability"] <= 1.0


# ---------------------------------------------------------------------------
# compute_behavioral_forecast — unified shape, determinism, empties
# ---------------------------------------------------------------------------

def test_unified_forecast_shape_and_json():
    actions = [_ev("1", "prune", 1.0), _ev("2", "edit", 2.0), _ev("3", "prune", 3.0)]
    motifs = _motifs(action_loops=[["edit", "prune"]])
    forecast = compute_behavioral_forecast(actions, motifs, build_graph([], []), {})
    assert set(forecast.keys()) == {
        "next_actions", "habit_trajectory", "trigger_likelihood", "loop_continuation",
    }
    json.dumps(forecast)                                     # JSON-serialisable


def test_forecast_deterministic():
    actions = [
        _ev("e0", "edit", 10.0, 0.5), _ev("e1", "edit", 20.0, 0.5),
        _ev("e2", "edit", 30.0, 0.5), _ev("p0", "prune", 40.0),
    ]
    motifs = _motifs(
        action_loops=[["edit", "prune"]], habits=["edit"],
        trigger_chains=[["e0", "factor_0", "p0"]],
    )
    graph = build_graph([make_node("e2", "action", "edit")], [])
    influence = {"e2": 0.5}
    a = compute_behavioral_forecast(actions, motifs, graph, influence)
    b = compute_behavioral_forecast(actions, motifs, graph, influence)
    assert a == b


def test_forecast_empty_inputs():
    assert compute_behavioral_forecast([], EMPTY_MOTIFS, build_graph([], []), {}) == {
        "next_actions": [],
        "habit_trajectory": [],
        "trigger_likelihood": [],
        "loop_continuation": [],
    }


def test_no_randomness_or_wallclock():
    # Structural guard: the engine pulls in no randomness / wall-clock source.
    src = inspect.getsource(__import__("phase10_forecast"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
