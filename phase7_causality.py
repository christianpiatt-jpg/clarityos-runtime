# phase7_causality.py
"""
Phase 7.7 — Causal Drift Mapping (Phase 7 causality layer).

Pure, deterministic, DIAGNOSTIC layer: given a telemetry history and a log of
recent operator actions, it identifies which actions correlate with drift /
coherence movement. It assigns no blame, prescribes nothing, and changes no
behavior — it answers "what likely contributed to the drift we're seeing?"

    compute_causal_factors(history, recent_actions) -> list[CausalFactor]

Method (deterministic; documented in phase7_spec.md "Phase 7.7"):
  * Consider the last WINDOW (=10) actions.
  * Build per-interval drift / coherence deltas from the history.
  * For each action, split the intervals at the action's timestamp into BEFORE
    (interval end <= t_action) and AFTER (interval end > t_action), and measure
    the *shift* in mean delta: how much more drift moved (and coherence fell)
    after the action than before.
  * correlation  = clamp(drift_shift, -1, 1)        # signed
  * contribution = clamp((max(0, drift_shift) + max(0, -coherence_shift)) / 2,
                         0, 1)                        # destabilizing magnitude
  * Drop factors below MIN_CONTRIBUTION; sort the rest by contribution desc.
    If none survive → a single ``CausalFactor("none", 0.0, 0.0)``.

No I/O, no wall-clock, no randomness, no side effects. The only import is the
Phase 7 record type — nothing from the CI-gated runtime spine.
"""
from dataclasses import dataclass

from phase7_storage import TelemetryRecord

# Most-recent actions considered.
WINDOW = 10

# Factors weaker than this are dropped from the output.
MIN_CONTRIBUTION = 0.05


@dataclass
class OperatorAction:
    """A single recent operator action. ``timestamp`` is caller-supplied (no
    wall-clock is read here); it is compared against telemetry timestamps."""
    action: str
    timestamp: float


@dataclass
class CausalFactor:
    """An action's correlation with, and contribution to, instability."""
    action: str
    correlation: float   # [-1, 1] — signed drift shift after the action
    contribution: float  # [0, 1]  — destabilizing magnitude


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _interval_deltas(history: list[TelemetryRecord]) -> list[tuple]:
    """``(end_timestamp, drift_delta, coherence_delta)`` per consecutive
    interval. An interval touching a ``None`` drift (the first record) carries
    ``drift_delta = 0.0`` — no measurable drift movement there."""
    out: list[tuple] = []
    for i in range(len(history) - 1):
        a, b = history[i], history[i + 1]
        if a.drift is None or b.drift is None:
            drift_delta = 0.0
        else:
            drift_delta = b.drift - a.drift
        ca = a.coherence_health if a.coherence_health is not None else 0.0
        cb = b.coherence_health if b.coherence_health is not None else 0.0
        out.append((b.timestamp, drift_delta, cb - ca))
    return out


def _factor_for_action(action: OperatorAction, deltas: list[tuple]) -> CausalFactor:
    after_drift = [dd for (ts, dd, cd) in deltas if ts > action.timestamp]
    if not after_drift:
        # Nothing happened after the action — no measurable effect.
        return CausalFactor(action.action, 0.0, 0.0)
    after_coh = [cd for (ts, dd, cd) in deltas if ts > action.timestamp]
    before_drift = [dd for (ts, dd, cd) in deltas if ts <= action.timestamp]
    before_coh = [cd for (ts, dd, cd) in deltas if ts <= action.timestamp]

    drift_shift = _clamp(_mean(after_drift) - _mean(before_drift), -1.0, 1.0)
    coherence_shift = _clamp(_mean(after_coh) - _mean(before_coh), -1.0, 1.0)

    correlation = drift_shift
    contribution = _clamp(
        (max(0.0, drift_shift) + max(0.0, -coherence_shift)) / 2.0, 0.0, 1.0
    )
    return CausalFactor(action.action, correlation, contribution)


def compute_causal_factors(
    history: list[TelemetryRecord],
    recent_actions: list[OperatorAction],
) -> list[CausalFactor]:
    """Return causal factors for the last ``WINDOW`` actions, strongest first.

    Factors with ``contribution < MIN_CONTRIBUTION`` are dropped; if none
    survive (including when there are no actions or no history), a single
    neutral ``CausalFactor("none", 0.0, 0.0)`` is returned.
    """
    deltas = _interval_deltas(history)
    factors = [_factor_for_action(a, deltas) for a in recent_actions[-WINDOW:]]
    significant = [f for f in factors if f.contribution >= MIN_CONTRIBUTION]
    if not significant:
        return [CausalFactor("none", 0.0, 0.0)]
    return sorted(significant, key=lambda f: f.contribution, reverse=True)
