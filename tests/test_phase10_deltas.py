# tests/test_phase10_deltas.py
#
# CARD 10.1 — Action-Causal Deltas: frequency / spacing / influence / centrality
# deltas + the unified behavioral-delta object.
#
# Pure / deterministic — no storage, no client, no wall-clock. Windows are
# anchored at the latest timestamp in the input (caller supplies timestamps).
import inspect
import json

import pytest

from phase9_actions import ActionEvent
from phase9_influence import InfluenceRecord
from phase10_deltas import (
    compute_action_centrality_delta,
    compute_action_frequency_delta,
    compute_action_influence_delta,
    compute_action_spacing_delta,
    compute_behavioral_deltas,
)


def _ev(id, label, ts, mag=None):
    return ActionEvent(id=id, label=label, timestamp=ts, magnitude=mag)


# ---------------------------------------------------------------------------
# Frequency delta
# ---------------------------------------------------------------------------

def test_frequency_delta():
    # window 10, t_ref = 100 → current (90, 100], previous (80, 90].
    actions = [
        _ev("p1", "prune", 95.0), _ev("p2", "prune", 98.0), _ev("p3", "prune", 100.0),  # current x3
        _ev("p0", "prune", 85.0),                                                        # previous x1
        _ev("e1", "edit", 92.0),                                                         # current x1
        _ev("e2", "edit", 82.0), _ev("e3", "edit", 88.0),                                # previous x2
    ]
    result = compute_action_frequency_delta(actions, 10.0)
    assert result["prune"]["current"] == 3
    assert result["prune"]["previous"] == 1
    assert result["prune"]["delta"] == pytest.approx(2.0)        # (3 - 1) / max(1, 1)
    assert result["edit"]["current"] == 1
    assert result["edit"]["previous"] == 2
    assert result["edit"]["delta"] == pytest.approx(-0.5)        # (1 - 2) / max(2, 1)


def test_frequency_delta_empty():
    assert compute_action_frequency_delta([], 10.0) == {}


# ---------------------------------------------------------------------------
# Spacing delta (positive = tightening)
# ---------------------------------------------------------------------------

def test_spacing_delta_tightening():
    # previous spacing 10, current spacing 2 → spacing decreased → positive delta.
    actions = [
        _ev("s1", "sync", 10.0), _ev("s2", "sync", 20.0), _ev("s3", "sync", 30.0),  # previous
        _ev("s4", "sync", 62.0), _ev("s5", "sync", 64.0), _ev("s6", "sync", 66.0),  # current
    ]
    entry = compute_action_spacing_delta(actions, 30.0)["sync"]
    assert entry["current_spacing"] == pytest.approx(2.0)
    assert entry["previous_spacing"] == pytest.approx(10.0)
    assert entry["delta"] == pytest.approx(0.8)                  # (10 - 2) / max(10, 1)


def test_spacing_delta_loosening():
    # previous spacing 2, current spacing 10 → spacing increased → negative delta.
    actions = [
        _ev("s1", "sync", 42.0), _ev("s2", "sync", 44.0), _ev("s3", "sync", 46.0),  # previous
        _ev("s4", "sync", 60.0), _ev("s5", "sync", 70.0), _ev("s6", "sync", 80.0),  # current
    ]
    entry = compute_action_spacing_delta(actions, 30.0)["sync"]
    assert entry["current_spacing"] == pytest.approx(10.0)
    assert entry["previous_spacing"] == pytest.approx(2.0)
    assert entry["delta"] == pytest.approx(-4.0)                 # (2 - 10) / max(2, 1)


# ---------------------------------------------------------------------------
# Influence delta
# ---------------------------------------------------------------------------

def test_influence_delta():
    # window 10, t_ref = 100 → current (90, 100], previous (80, 90].
    records = [
        InfluenceRecord("a1", "v1", 0.5, 100.0),
        InfluenceRecord("a1", "v2", 0.3, 100.0),    # a1 current sum = 0.8
        InfluenceRecord("a0", "v1", 0.4, 85.0),     # a0 previous sum = 0.4
    ]
    result = compute_action_influence_delta(records, 10.0)
    assert result["a1"]["current"] == pytest.approx(0.8)
    assert result["a1"]["previous"] == 0.0
    assert result["a1"]["delta"] == pytest.approx(0.8)          # (0.8 - 0) / max(0, 1)
    assert result["a0"]["current"] == 0.0
    assert result["a0"]["previous"] == pytest.approx(0.4)
    assert result["a0"]["delta"] == pytest.approx(-0.4)         # (0 - 0.4) / max(0.4, 1)


def test_influence_delta_empty():
    assert compute_action_influence_delta([], 10.0) == {}


# ---------------------------------------------------------------------------
# Centrality delta (current - previous)
# ---------------------------------------------------------------------------

def test_centrality_delta():
    current = {"a1": 0.8, "a2": 0.3, "a3": 0.5}
    previous = {"a1": 0.6, "a2": 0.3, "a4": 0.2}
    result = compute_action_centrality_delta(current, previous)
    assert result["a1"]["current"] == 0.8
    assert result["a1"]["previous"] == 0.6
    assert result["a1"]["delta"] == pytest.approx(0.2)
    assert result["a2"]["delta"] == pytest.approx(0.0)          # unchanged
    # a3 only in current → previous 0, positive delta.
    assert result["a3"]["previous"] == 0.0
    assert result["a3"]["delta"] == pytest.approx(0.5)
    # a4 only in previous → current 0, negative delta.
    assert result["a4"]["current"] == 0.0
    assert result["a4"]["delta"] == pytest.approx(-0.2)


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------

def test_deterministic_ordering():
    actions = [_ev("x0", "zebra", 90.0), _ev("x1", "alpha", 91.0), _ev("x2", "mid", 92.0)]
    keys = list(compute_action_frequency_delta(actions, 100.0).keys())
    assert keys == ["alpha", "mid", "zebra"]                    # sorted, not insertion order


def test_centrality_delta_sorted_keys():
    result = compute_action_centrality_delta({"z": 0.1, "a": 0.2}, {"m": 0.3})
    assert list(result.keys()) == ["a", "m", "z"]


# ---------------------------------------------------------------------------
# Unified delta object
# ---------------------------------------------------------------------------

def test_unified_delta_shape_and_json():
    actions = [_ev("p1", "prune", 100.0), _ev("p0", "prune", 85.0)]
    records = [InfluenceRecord("p1", "v1", 0.5, 100.0)]
    centrality = {"p1": 0.7}
    deltas = compute_behavioral_deltas(actions, records, centrality, 10.0)
    assert set(deltas.keys()) == {"frequency", "spacing", "influence", "centrality"}
    json.dumps(deltas)                                          # JSON-serialisable


def test_unified_with_prev_centrality():
    deltas = compute_behavioral_deltas([], [], {"a1": 0.8}, 10.0, prev_centrality={"a1": 0.5})
    assert deltas["centrality"]["a1"]["delta"] == pytest.approx(0.3)


def test_unified_centrality_defaults_to_empty_previous():
    deltas = compute_behavioral_deltas([], [], {"a1": 0.8}, 10.0)
    assert deltas["centrality"]["a1"]["previous"] == 0.0
    assert deltas["centrality"]["a1"]["delta"] == pytest.approx(0.8)


def test_unified_empty_inputs():
    assert compute_behavioral_deltas([], [], {}, 10.0) == {
        "frequency": {}, "spacing": {}, "influence": {}, "centrality": {},
    }


def test_deltas_deterministic():
    actions = [_ev("p1", "prune", 100.0), _ev("p0", "prune", 85.0), _ev("e1", "edit", 95.0)]
    records = [InfluenceRecord("p1", "v1", 0.5, 100.0), InfluenceRecord("p0", "v1", 0.2, 85.0)]
    centrality = {"p1": 0.7, "e1": 0.4}
    a = compute_behavioral_deltas(actions, records, centrality, 10.0, prev_centrality={"p1": 0.5})
    b = compute_behavioral_deltas(actions, records, centrality, 10.0, prev_centrality={"p1": 0.5})
    assert a == b


# ---------------------------------------------------------------------------
# No randomness / no wall-clock (structural guard)
# ---------------------------------------------------------------------------

def test_no_randomness_or_wallclock():
    src = inspect.getsource(__import__("phase10_deltas"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
