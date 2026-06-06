# phase10_stability.py
"""
Phase 10.2 — Behavioral Stability Forecast.

The behavioral analogue of Phase 7.2 (temporal stability) and Phase 8.7 (causal
stability forecast), but for *actions*: it folds the 10.1 deltas, the 9.4
motifs, and the 10.0 forecast into a single ``[0, 1]`` stability score plus the
four drivers behind it.

    compute_behavioral_stability(deltas, motifs, forecast) -> dict

Output::

    {"score": <float in [0, 1]>,
     "drivers": {"habit_stability":   <float in [0, 1]>,
                 "trigger_stability": <float in [0, 1]>,
                 "loop_persistence":  <float in [0, 1]>,
                 "action_variance":   <float in [0, 1]>}}

Components (each clamped to ``[0, 1]``):
  * habit_stability   = 1 - mean(|frequency delta|)             (10.1 frequency)
  * trigger_stability = 1 - mean(|trigger likelihood|)          (10.0 forecast)
  * loop_persistence  = mean(loop continuation probability)     (10.0 forecast)
  * action_variance   = 1 - variance(frequency delta)           (10.1 frequency)

Final score (weights sum to 1.0)::

    score = 0.35*habit_stability + 0.25*trigger_stability
          + 0.25*loop_persistence + 0.15*action_variance

Note on the trigger driver: neither 10.0 nor 10.1 produces a *temporal*
trigger-likelihood delta (there is no prior-forecast snapshot to diff against),
so trigger volatility is taken as the mean trigger-likelihood from the 10.0
forecast — each chain's likelihood is the magnitude of the behavioral shift it
would drive. A future card that snapshots forecasts could swap in a true
temporal delta without changing this contract.

``motifs`` is accepted for signature parity with the 10.x behavioral API (and
future motif-weighted scoring); 10.2's four components read the 10.1 deltas +
10.0 forecast only.

Pure / deterministic: no I/O, wall-clock, randomness, ML, or inference. Imports
only the stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state; no operator_state writes, no new continuity buckets.

See ``phase10_spec.md`` ("Phase 10.2 — Behavioral Stability Forecast").
"""
import statistics

# Component weights (sum = 1.0).
HABIT_WEIGHT = 0.35
TRIGGER_WEIGHT = 0.25
LOOP_WEIGHT = 0.25
VARIANCE_WEIGHT = 0.15


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mean_abs(values) -> float:
    """Mean absolute value of ``values`` (0.0 for an empty iterable)."""
    values = [abs(float(v)) for v in values]
    return sum(values) / len(values) if values else 0.0


def _mean(values) -> float:
    """Arithmetic mean of ``values`` (0.0 for an empty iterable)."""
    values = [float(v) for v in values]
    return sum(values) / len(values) if values else 0.0


def _frequency_deltas(deltas: dict) -> list:
    """The 10.1 per-label frequency ``delta`` values (``[]`` when absent)."""
    frequency = (deltas or {}).get("frequency") or {}
    return [float(entry.get("delta", 0.0)) for entry in frequency.values()]


def compute_behavioral_stability(deltas: dict, motifs: dict, forecast: dict) -> dict:
    """Deterministic behavioral stability score + driver breakdown.

    See the module docstring for the four component formulas and the weighting.
    An all-empty input scores ``0.75`` (the three volatility drivers read 1.0 —
    no change is maximal stability — while ``loop_persistence`` reads 0.0, since
    no detected loop means no demonstrated loop persistence). Output is
    JSON-serialisable.
    """
    deltas = deltas or {}
    forecast = forecast or {}

    freq_deltas = _frequency_deltas(deltas)

    # (1) Habit stability — inverse of the mean absolute frequency delta.
    habit_stability = _clamp(1.0 - _mean_abs(freq_deltas), 0.0, 1.0)

    # (2) Trigger stability — inverse of the mean trigger likelihood (the
    #     volatility signal, see the module note).
    trigger_likelihoods = [
        t.get("likelihood", 0.0) for t in (forecast.get("trigger_likelihood") or [])
    ]
    trigger_stability = _clamp(1.0 - _mean_abs(trigger_likelihoods), 0.0, 1.0)

    # (3) Loop persistence — mean loop-continuation probability (already [0, 1]).
    loop_probs = [
        loop.get("continuation_probability", 0.0)
        for loop in (forecast.get("loop_continuation") or [])
    ]
    loop_persistence = _clamp(_mean(loop_probs), 0.0, 1.0)

    # (4) Action variance — inverse of the (population) variance of the
    #     frequency deltas; the outer clamp normalizes it to [0, 1].
    variance = statistics.pvariance(freq_deltas) if len(freq_deltas) >= 2 else 0.0
    action_variance = _clamp(1.0 - variance, 0.0, 1.0)

    score = _clamp(
        HABIT_WEIGHT * habit_stability
        + TRIGGER_WEIGHT * trigger_stability
        + LOOP_WEIGHT * loop_persistence
        + VARIANCE_WEIGHT * action_variance,
        0.0, 1.0,
    )

    return {
        "score": score,
        "drivers": {
            "habit_stability": habit_stability,
            "trigger_stability": trigger_stability,
            "loop_persistence": loop_persistence,
            "action_variance": action_variance,
        },
    }
