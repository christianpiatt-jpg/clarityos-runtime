# tests/test_phase10_stability.py
#
# CARD 10.2 — Behavioral Stability Forecast: the [0,1] stability score + its four
# drivers (habit / trigger / loop / variance) from the 10.1 deltas + 10.0
# forecast.
#
# Pure / deterministic — no storage, no client, no wall-clock.
import inspect
import json

import pytest

from phase10_stability import (
    HABIT_WEIGHT,
    LOOP_WEIGHT,
    TRIGGER_WEIGHT,
    VARIANCE_WEIGHT,
    compute_behavioral_stability,
)


def _freq(*deltas):
    """A 10.1-shaped frequency-delta dict from raw delta values."""
    return {"frequency": {f"a{i}": {"current": 0, "previous": 0, "delta": d}
                          for i, d in enumerate(deltas)}}


# ---------------------------------------------------------------------------
# Individual drivers
# ---------------------------------------------------------------------------

def test_habit_stability():
    # mean(|0.5|, |-0.5|) = 0.5 → habit_stability = 1 - 0.5 = 0.5.
    result = compute_behavioral_stability(_freq(0.5, -0.5), {}, {})
    assert result["drivers"]["habit_stability"] == pytest.approx(0.5)


def test_habit_stability_clamped():
    # mean(|5.0|) = 5.0 → 1 - 5 = -4 → clamped to 0.0.
    result = compute_behavioral_stability(_freq(5.0), {}, {})
    assert result["drivers"]["habit_stability"] == 0.0


def test_trigger_stability():
    forecast = {"trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.4},
                                       {"chain": ["c", "f", "d"], "likelihood": 0.6}]}
    result = compute_behavioral_stability({}, {}, forecast)
    # mean(0.4, 0.6) = 0.5 → trigger_stability = 1 - 0.5 = 0.5.
    assert result["drivers"]["trigger_stability"] == pytest.approx(0.5)


def test_loop_persistence():
    forecast = {"loop_continuation": [{"loop": ["a", "b"], "continuation_probability": 0.8},
                                      {"loop": ["c", "d"], "continuation_probability": 0.6}]}
    result = compute_behavioral_stability({}, {}, forecast)
    assert result["drivers"]["loop_persistence"] == pytest.approx(0.7)


def test_action_variance():
    # pvariance(0.5, -0.5) = 0.25 → action_variance = 1 - 0.25 = 0.75.
    result = compute_behavioral_stability(_freq(0.5, -0.5), {}, {})
    assert result["drivers"]["action_variance"] == pytest.approx(0.75)


def test_action_variance_zero_for_constant_deltas():
    # all-equal deltas → variance 0 → action_variance = 1.0.
    result = compute_behavioral_stability(_freq(0.3, 0.3, 0.3), {}, {})
    assert result["drivers"]["action_variance"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Weighted score
# ---------------------------------------------------------------------------

def test_weighted_score():
    deltas = _freq(0.5, -0.5)              # habit 0.5, variance 0.75
    forecast = {
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.5}],   # trigger 0.5
        "loop_continuation": [{"loop": ["a", "b"], "continuation_probability": 0.7}],  # loop 0.7
    }
    result = compute_behavioral_stability(deltas, {}, forecast)
    drivers = result["drivers"]
    assert drivers["habit_stability"] == pytest.approx(0.5)
    assert drivers["trigger_stability"] == pytest.approx(0.5)
    assert drivers["loop_persistence"] == pytest.approx(0.7)
    assert drivers["action_variance"] == pytest.approx(0.75)
    expected = (
        HABIT_WEIGHT * 0.5 + TRIGGER_WEIGHT * 0.5
        + LOOP_WEIGHT * 0.7 + VARIANCE_WEIGHT * 0.75
    )
    assert result["score"] == pytest.approx(expected)         # 0.5875


def test_score_and_drivers_in_unit_range():
    deltas = _freq(0.2, -0.9, 1.5)
    forecast = {
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.9}],
        "loop_continuation": [{"loop": ["a", "b"], "continuation_probability": 0.3}],
    }
    result = compute_behavioral_stability(deltas, {}, forecast)
    assert 0.0 <= result["score"] <= 1.0
    for value in result["drivers"].values():
        assert 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# Shape, empties, determinism
# ---------------------------------------------------------------------------

def test_shape_and_json():
    result = compute_behavioral_stability({}, {}, {})
    assert set(result.keys()) == {"score", "drivers"}
    assert set(result["drivers"].keys()) == {
        "habit_stability", "trigger_stability", "loop_persistence", "action_variance",
    }
    json.dumps(result)


def test_empty_inputs_score():
    # No change on the three volatility axes → 1.0; no loops → loop_persistence 0.0.
    result = compute_behavioral_stability({}, {}, {})
    assert result["drivers"]["habit_stability"] == 1.0
    assert result["drivers"]["trigger_stability"] == 1.0
    assert result["drivers"]["loop_persistence"] == 0.0
    assert result["drivers"]["action_variance"] == 1.0
    # 0.35*1 + 0.25*1 + 0.25*0 + 0.15*1 = 0.75
    assert result["score"] == pytest.approx(0.75)


def test_none_inputs_safe():
    result = compute_behavioral_stability(None, None, None)
    assert result["score"] == pytest.approx(0.75)


def test_deterministic():
    deltas = _freq(0.5, -0.5)
    forecast = {
        "trigger_likelihood": [{"chain": ["a", "f", "b"], "likelihood": 0.5}],
        "loop_continuation": [{"loop": ["a", "b"], "continuation_probability": 0.7}],
    }
    a = compute_behavioral_stability(deltas, {"habits": ["x"]}, forecast)
    b = compute_behavioral_stability(deltas, {"habits": ["x"]}, forecast)
    assert a == b


def test_no_randomness_or_wallclock():
    src = inspect.getsource(__import__("phase10_stability"))
    for forbidden in (
        "import random", "from random", "import time", "from time",
        "import datetime", "from datetime", "perf_counter", "monotonic", "uuid",
    ):
        assert forbidden not in src
