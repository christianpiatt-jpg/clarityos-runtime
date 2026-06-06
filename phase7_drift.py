# phase7_drift.py
"""
Phase 7 — Drift & Trust-Center computations.

Pure, deterministic functions over Phase 6 ``SuperstructureState`` values:

  * compute_drift(prev, curr)            -> float in [0, 1]
  * compute_coherence_health(history)    -> float in [0, 1]
  * compute_trust_band(drift, coherence) -> "LOW" | "MEDIUM" | "HIGH"

No I/O, no wall-clock, no randomness. The only import is the Phase 6
contract module (``phase6_contracts``) for the ``SuperstructureState`` type —
nothing from the CI-gated runtime spine.

See ``phase7_spec.md`` for the formal definitions these implement.
"""
from phase6_contracts import SuperstructureState


# --- Tunable constants (kept explicit so the spec + tests can pin them) -----

# compute_drift blends quantitative movement (the 13 numeric fields) with
# qualitative movement (the categorical identity anchors). The weights sum to
# 1.0 so the blended score is already in [0, 1].
DRIFT_NUMERIC_WEIGHT = 0.7
DRIFT_LABEL_WEIGHT = 0.3

# compute_trust_band cut points on the trust score, coherence * (1 - drift).
TRUST_HIGH_THRESHOLD = 0.66
TRUST_MEDIUM_THRESHOLD = 0.33


def _clamp01(x: float) -> float:
    """Clamp a float to the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, x))


def _mean(values: list[float]) -> float:
    """Arithmetic mean; an empty sequence has no signal and yields 0.0."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _numeric_vector(state: SuperstructureState) -> list[float]:
    """The 13 quantitative Phase 6 signals, in a fixed order.

    Every value is produced by Phase 6 in [0, 1]; this ordering is the
    canonical comparison basis for drift.
    """
    return [
        state.pattern.pattern_strength,
        state.pattern.pattern_stability,
        state.pattern.pattern_coherence,
        state.integration.integration_strength,
        state.integration.cross_layer_alignment,
        state.coherence.coherence_level,
        state.coherence.drift_resistance,
        state.coherence.load_resilience,
        state.essence.essence_signal,
        state.essence.essence_clarity,
        state.identity.identity_strength,
        state.identity.identity_stability,
        state.identity.identity_projection,
    ]


def _identity_anchors(state: SuperstructureState) -> list[str]:
    """The categorical identity anchors that define *who* the operator is.

    These are the semantic labels — not the formatted composite identity
    strings (``pattern_identity`` / ``coherence_identity`` / ...), which
    already embed the numeric values and would double-count quantitative
    movement.
    """
    return [
        state.pattern.dominant_pattern,
        state.essence.invariant_identity,
        state.identity.operator_identity,
    ]


def compute_drift(prev: SuperstructureState, curr: SuperstructureState) -> float:
    """How much Phase 6 identity moved between two snapshots, in [0, 1].

    A blend of:
      * numeric_drift — mean absolute difference across the 13 numeric
        signals (each in [0, 1], so the mean is in [0, 1]).
      * label_drift   — fraction of identity anchors that changed.

        drift = DRIFT_NUMERIC_WEIGHT * numeric_drift
              + DRIFT_LABEL_WEIGHT   * label_drift

    0.0 means the two snapshots are identical; 1.0 means every numeric signal
    moved the full range *and* every identity anchor changed.
    """
    prev_vec = _numeric_vector(prev)
    curr_vec = _numeric_vector(curr)
    numeric_drift = _mean([abs(c - p) for p, c in zip(prev_vec, curr_vec)])

    prev_labels = _identity_anchors(prev)
    curr_labels = _identity_anchors(curr)
    changed = sum(1 for p, c in zip(prev_labels, curr_labels) if p != c)
    label_drift = changed / len(prev_labels) if prev_labels else 0.0

    drift = DRIFT_NUMERIC_WEIGHT * numeric_drift + DRIFT_LABEL_WEIGHT * label_drift
    return _clamp01(drift)


def _coherence_signal(state: SuperstructureState) -> float:
    """A single per-snapshot coherence/essence/identity signal in [0, 1].

    The mean of the nine Phase 6 fields that speak to whether the operator is
    internally coherent, retains its essence, and holds its identity.
    """
    return _mean([
        state.pattern.pattern_coherence,
        state.coherence.coherence_level,
        state.coherence.drift_resistance,
        state.coherence.load_resilience,
        state.essence.essence_signal,
        state.essence.essence_clarity,
        state.identity.identity_strength,
        state.identity.identity_stability,
        state.identity.identity_projection,
    ])


def compute_coherence_health(history: list[SuperstructureState]) -> float:
    """Rolling coherence/essence/identity health across a history, in [0, 1].

    The equal-weighted mean of each snapshot's coherence signal. An empty
    history has no established health and returns 0.0. (Movement over time is
    measured separately by ``compute_drift``; recency weighting is a
    deliberate future refinement — see ``phase7_spec.md``.)
    """
    if not history:
        return 0.0
    return _clamp01(_mean([_coherence_signal(s) for s in history]))


def compute_trust_band(drift: float, coherence: float) -> str:
    """Map a (drift, coherence) pair to a trust band.

    ``trust_score = coherence * (1 - drift)``, so trust rises with coherence
    and falls as drift grows. Inputs are expected in [0, 1] and are clamped
    defensively.

        trust_score >= TRUST_HIGH_THRESHOLD   -> "HIGH"
        trust_score >= TRUST_MEDIUM_THRESHOLD -> "MEDIUM"
        otherwise                             -> "LOW"
    """
    trust_score = _clamp01(coherence) * (1.0 - _clamp01(drift))
    if trust_score >= TRUST_HIGH_THRESHOLD:
        return "HIGH"
    if trust_score >= TRUST_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"
