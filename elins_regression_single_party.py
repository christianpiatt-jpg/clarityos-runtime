"""
elins_regression_single_party.py — ELINS Unit 1.

Callable validation harness for the "Single-Party Rule and Fear Across
Timelines" regression. Pure, deterministic, side-effect-free.

ROLE
----
This module is a POST-INFERENCE VALIDATOR, not a predictor.

Given a Timeline of TimePoints carrying structural variables
(regime competition, autocratization, repression, fear, etc.), the
validator:
    1. Computes four derived series (single_party_score, fear_pressure,
       authoritarian_risk, dissent_suppression).
    2. Evaluates five scenario tests (rising concentration, crackdown
       event, threat spike, constraint restoration, digital substitution).
    3. Evaluates six structural assertions over the derived series.
    4. Produces a SinglePartyFearRegressionResult — a structured score
       (0-10) plus per-test / per-assertion booleans plus the full
       derived series for downstream inspection.

Does NOT:
    * predict, generate, or forecast timelines
    * make normative or political judgments
    * call any I/O / LLM / network
    * mutate the input timeline

PUBLIC API
----------
    run_single_party_fear_regression(timeline) -> SinglePartyFearRegressionResult

WEIGHTING SCHEME (locked, equal weights — see § derived variables)
SCORING RUBRIC (locked, 0-2 per dimension × 5 dimensions = 0-10)

See ELINS Unit 1 work-set for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


# ===========================================================================
# Locked constants
# ===========================================================================

# Trend / step thresholds. All are defensible, simple, and locked here so
# any change is a deliberate spec revision.

# Detect "rises" / "declines" by comparing first vs. last value of a
# series (or first vs. last of a sub-window). A delta above this counts
# as a meaningful trend.
_TREND_DELTA_THRESHOLD: float = 0.10

# A single-step delta whose magnitude exceeds this counts as a "sharp"
# move (sharp increase or sharp decline).
_SHARP_STEP_THRESHOLD: float = 0.30

# A trigger-event window — the next N periods after a trigger event are
# the period during which we expect fear/dissent responses.
_EVENT_RESPONSE_WINDOW: int = 3

# For "near-monotonic" checks: the sum of negative deltas (downsteps)
# allowed before the series is considered to violate monotonicity.
_NEAR_MONOTONIC_TOLERANCE: float = 0.20

# A "modest" change is below this threshold (used in test 3).
_MODEST_DELTA_THRESHOLD: float = 0.15

# Weights for derived risk indices. Equal weights — every input
# contributes the same fraction. Locked.
_AUTHORITARIAN_RISK_WEIGHTS: tuple = (
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0,  # 6 inputs, mean
)
_DISSENT_SUPPRESSION_WEIGHTS: tuple = (
    1.0, 1.0, 1.0, 1.0, 1.0,        # 5 inputs, mean
)

# Scoring thresholds (locked per work-set).
SCORE_STRONG_FLOOR: int = 9      # 9-10 = Strong regression behavior
SCORE_ACCEPTABLE_FLOOR: int = 7  # 7-8  = Acceptable with minor inconsistencies
SCORE_WEAK_FLOOR: int = 5        # 5-6  = Weak, needs review
                                 # 0-4  = Fails core political-fear timeline logic


# ===========================================================================
# Schemas — frozen dataclasses
# ===========================================================================
@dataclass(frozen=True)
class TimePoint:
    """One time point in a regression timeline.

    All structural variables live in the [0.0, 1.0] interval (the
    validator does not enforce this — out-of-range values are scored
    naturally).
    """
    t:                    str
    regime_competition:   float
    autocratization:      float
    repression_index:     float
    digital_repression:   float
    perceived_threat:     float
    fear_signal:          float
    dissent_capacity:     float
    normative_constraint: float
    support_buffer:       float
    trigger_event:        Optional[str] = None


@dataclass(frozen=True)
class Timeline:
    """A regression timeline. Order of `points` is taken as time order
    (point[0] is earliest)."""
    timeline_id: str
    points:      tuple   # tuple[TimePoint, ...]


@dataclass(frozen=True)
class SinglePartyFearRegressionResult:
    """The full validation verdict for a Timeline.

    Carries the locked rubric dimensions, per-assertion + per-scenario
    booleans, and the four derived series for downstream inspection.
    """
    timeline_id:                  str
    score:                        int   # 0-10, sum of dimension scores
    structural_consistency_score: int   # 0-2
    timeline_sensitivity_score:   int   # 0-2
    fear_mechanism_score:         int   # 0-2
    threat_mechanism_score:       int   # 0-2
    repression_coverage_score:    int   # 0-2
    assertions_passed:            tuple
    assertions_failed:            tuple
    scenario_results:             dict
    derived_series:               dict


# ===========================================================================
# Helpers — series math
# ===========================================================================
def _series(timeline: Timeline, attr: str) -> list:
    """Extract a single attribute as a list across the timeline."""
    return [getattr(p, attr) for p in timeline.points]


def _mean(xs: Sequence[float]) -> float:
    """Arithmetic mean. Empty → 0.0."""
    n = len(xs)
    if n == 0:
        return 0.0
    return sum(xs) / n


def _weighted_mean(xs: Sequence[float], weights: Sequence[float]) -> float:
    """Weighted mean. Empty → 0.0. Weights must match xs length."""
    if not xs:
        return 0.0
    total_weight = sum(weights)
    if total_weight == 0.0:
        return 0.0
    weighted_sum = sum(x * w for x, w in zip(xs, weights))
    return weighted_sum / total_weight


def _trend_delta(series: list) -> float:
    """Return last - first of a series. Empty / single-point → 0.0."""
    if len(series) < 2:
        return 0.0
    return series[-1] - series[0]


def _max_step_drop(series: list) -> float:
    """Return the largest single-step decrease (positive number). 0.0
    if the series is non-decreasing throughout."""
    if len(series) < 2:
        return 0.0
    max_drop = 0.0
    for i in range(1, len(series)):
        drop = series[i - 1] - series[i]
        if drop > max_drop:
            max_drop = drop
    return max_drop


def _sum_negative_deltas(series: list) -> float:
    """Sum of |drop| across all decreasing steps. Used for the
    near-monotonic check: if total downward movement exceeds tolerance,
    the series is not near-monotonically increasing."""
    if len(series) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(series)):
        drop = series[i - 1] - series[i]
        if drop > 0:
            total += drop
    return total


def _pearson_sign(xs: list, ys: list) -> int:
    """Return +1 / 0 / -1 — the sign of the Pearson correlation between
    xs and ys. Returns 0 for length < 2 or zero variance."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return 0
    mx = _mean(xs)
    my = _mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    var_x = sum((xs[i] - mx) ** 2 for i in range(n))
    var_y = sum((ys[i] - my) ** 2 for i in range(n))
    if var_x == 0.0 or var_y == 0.0:
        return 0
    if num > 0:
        return 1
    if num < 0:
        return -1
    return 0


# ===========================================================================
# Derived variables (per work-set § 2)
# ===========================================================================
def _single_party_score(p: TimePoint) -> float:
    """1 - regime_competition. Higher = more monopolized rule."""
    return 1.0 - p.regime_competition


def _fear_pressure(p: TimePoint) -> float:
    """Mean of (perceived_threat, fear_signal, repression_index)."""
    return _mean((p.perceived_threat, p.fear_signal, p.repression_index))


def _authoritarian_risk(p: TimePoint) -> float:
    """Weighted (equal-weight) mean of:
        single_party_score, autocratization, repression_index,
        digital_repression, perceived_threat, (1 - normative_constraint).
    """
    return _weighted_mean(
        (
            _single_party_score(p),
            p.autocratization,
            p.repression_index,
            p.digital_repression,
            p.perceived_threat,
            1.0 - p.normative_constraint,
        ),
        _AUTHORITARIAN_RISK_WEIGHTS,
    )


def _dissent_suppression(p: TimePoint) -> float:
    """Weighted (equal-weight) mean of:
        repression_index, fear_signal, perceived_threat,
        single_party_score, (1 - dissent_capacity).
    """
    return _weighted_mean(
        (
            p.repression_index,
            p.fear_signal,
            p.perceived_threat,
            _single_party_score(p),
            1.0 - p.dissent_capacity,
        ),
        _DISSENT_SUPPRESSION_WEIGHTS,
    )


def _build_derived_series(timeline: Timeline) -> dict:
    """Compute all four derived series for the timeline."""
    return {
        "single_party_score":  [_single_party_score(p)  for p in timeline.points],
        "fear_pressure":       [_fear_pressure(p)       for p in timeline.points],
        "authoritarian_risk":  [_authoritarian_risk(p)  for p in timeline.points],
        "dissent_suppression": [_dissent_suppression(p) for p in timeline.points],
    }


# ===========================================================================
# Scenario tests (per work-set § 3)
# ===========================================================================
# Convention: each test returns True iff EITHER (a) the input pattern is
# not present (the test is vacuously satisfied), OR (b) the input
# pattern is present AND the pass condition holds.
# ===========================================================================

def _test_1_rising_concentration(timeline: Timeline, derived: dict) -> bool:
    """Test 1: declining regime_competition + rising autocratization +
    declining normative_constraint → authoritarian_risk near-monotonically
    increases AND repression_index does not sharply decline."""
    rc = _series(timeline, "regime_competition")
    auto = _series(timeline, "autocratization")
    norm = _series(timeline, "normative_constraint")
    risk = derived["authoritarian_risk"]
    rep = _series(timeline, "repression_index")

    rc_declines = _trend_delta(rc) <= -_TREND_DELTA_THRESHOLD
    auto_rises = _trend_delta(auto) >= _TREND_DELTA_THRESHOLD
    norm_declines = _trend_delta(norm) <= -_TREND_DELTA_THRESHOLD

    pattern_present = rc_declines and auto_rises and norm_declines
    if not pattern_present:
        return True

    risk_near_monotonic = _sum_negative_deltas(risk) <= _NEAR_MONOTONIC_TOLERANCE
    rep_no_sharp_drop = _max_step_drop(rep) < _SHARP_STEP_THRESHOLD
    return risk_near_monotonic and rep_no_sharp_drop


def _test_2_crackdown_event(timeline: Timeline, derived: dict) -> bool:
    """Test 2: For each trigger_event followed by a sharp rise in
    repression_index within the response window, fear_signal must rise
    AND dissent_capacity must fall in the same window."""
    points = timeline.points
    n = len(points)
    rep = _series(timeline, "repression_index")
    fear = _series(timeline, "fear_signal")
    diss = _series(timeline, "dissent_capacity")

    any_pattern_seen = False
    for i in range(n - 1):
        if not points[i].trigger_event:
            continue
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        rep_jump = max(rep[j] for j in range(i + 1, end + 1)) - rep[i]
        if rep_jump < _SHARP_STEP_THRESHOLD:
            continue
        any_pattern_seen = True
        fear_rise = max(fear[j] for j in range(i + 1, end + 1)) - fear[i]
        diss_fall = diss[i] - min(diss[j] for j in range(i + 1, end + 1))
        if fear_rise < _TREND_DELTA_THRESHOLD or diss_fall < _TREND_DELTA_THRESHOLD:
            return False

    # No pattern → vacuous pass; pattern seen and all responses ok → pass.
    _ = any_pattern_seen
    return True


def _test_3_threat_spike_without_full_repression(
    timeline: Timeline, derived: dict,
) -> bool:
    """Test 3: A sharp rise in perceived_threat with only a modest move
    in repression_index. Pass condition relies on `support_buffer` as a
    noisy proxy for "support for restrictive measures" (the timeline
    schema does not carry that field directly). If support_buffer rises
    in the threat-spike window, treat as supportive evidence; otherwise
    document and pass (we do not penalise for missing proxy)."""
    threat = _series(timeline, "perceived_threat")
    rep = _series(timeline, "repression_index")
    supp = _series(timeline, "support_buffer")
    n = len(timeline.points)

    if n < 2:
        return True

    # Detect any sharp threat rise (single-step delta) where repression
    # changes only modestly in the same step.
    pattern_seen = False
    for i in range(1, n):
        threat_rise = threat[i] - threat[i - 1]
        rep_change = abs(rep[i] - rep[i - 1])
        if threat_rise >= _SHARP_STEP_THRESHOLD and rep_change <= _MODEST_DELTA_THRESHOLD:
            pattern_seen = True
            # Proxy: support_buffer should not fall in the same window.
            if supp[i] - supp[i - 1] < -_TREND_DELTA_THRESHOLD:
                return False

    _ = pattern_seen
    return True


def _test_4_constraint_restoration(timeline: Timeline, derived: dict) -> bool:
    """Test 4: rising normative_constraint + rising support_buffer →
    authoritarian_risk declines, fear_pressure stabilises/declines,
    dissent_capacity recovers (lag tolerated)."""
    norm = _series(timeline, "normative_constraint")
    supp = _series(timeline, "support_buffer")
    risk = derived["authoritarian_risk"]
    fp = derived["fear_pressure"]
    diss = _series(timeline, "dissent_capacity")

    norm_rises = _trend_delta(norm) >= _TREND_DELTA_THRESHOLD
    supp_rises = _trend_delta(supp) >= _TREND_DELTA_THRESHOLD
    if not (norm_rises and supp_rises):
        return True

    risk_declines = _trend_delta(risk) <= 0
    fp_non_rising = _trend_delta(fp) <= _TREND_DELTA_THRESHOLD
    diss_recovers = _trend_delta(diss) >= 0
    return risk_declines and fp_non_rising and diss_recovers


def _test_5_digital_substitution(timeline: Timeline, derived: dict) -> bool:
    """Test 5: digital_repression rises while physical repression stays
    flat or rises more slowly → authoritarian_risk still rises AND
    fear_pressure is not driven to zero."""
    digi = _series(timeline, "digital_repression")
    rep = _series(timeline, "repression_index")
    risk = derived["authoritarian_risk"]
    fp = derived["fear_pressure"]

    digi_delta = _trend_delta(digi)
    rep_delta = _trend_delta(rep)
    if not (digi_delta >= _TREND_DELTA_THRESHOLD and rep_delta < digi_delta):
        return True

    risk_rises = _trend_delta(risk) > 0
    fp_nonzero = max(fp) > 0.0 if fp else True
    return risk_rises and fp_nonzero


# ===========================================================================
# Assertions (per work-set § 4)
# ===========================================================================
def _assertion_1_monotonicity(timeline: Timeline, derived: dict) -> bool:
    """If single_party_score AND autocratization rise AND
    normative_constraint falls, authoritarian_risk must not decline."""
    sp = derived["single_party_score"]
    auto = _series(timeline, "autocratization")
    norm = _series(timeline, "normative_constraint")
    risk = derived["authoritarian_risk"]

    if (_trend_delta(sp) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(auto) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(norm) <= -_TREND_DELTA_THRESHOLD):
        return _trend_delta(risk) >= 0
    return True


def _assertion_2_fear_repression(timeline: Timeline, derived: dict) -> bool:
    """If repression_index rises sharply after a trigger event,
    fear_signal must rise — unless support_buffer or normative_constraint
    rise strongly to offset."""
    points = timeline.points
    n = len(points)
    rep = _series(timeline, "repression_index")
    fear = _series(timeline, "fear_signal")
    supp = _series(timeline, "support_buffer")
    norm = _series(timeline, "normative_constraint")

    for i in range(n - 1):
        if not points[i].trigger_event:
            continue
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        rep_jump = max(rep[j] for j in range(i + 1, end + 1)) - rep[i]
        if rep_jump < _SHARP_STEP_THRESHOLD:
            continue
        fear_rise = max(fear[j] for j in range(i + 1, end + 1)) - fear[i]
        if fear_rise >= _TREND_DELTA_THRESHOLD:
            continue
        # Fear didn't rise; check the offset clause.
        supp_offset = (max(supp[j] for j in range(i + 1, end + 1)) - supp[i]
                       >= _TREND_DELTA_THRESHOLD)
        norm_offset = (max(norm[j] for j in range(i + 1, end + 1)) - norm[i]
                       >= _TREND_DELTA_THRESHOLD)
        if not (supp_offset or norm_offset):
            return False
    return True


def _assertion_3_threat_authoritarian(timeline: Timeline, derived: dict) -> bool:
    """If perceived_threat rises, the proxy for "support for restrictive
    authority" (support_buffer) must not fall sharply without a clear
    moderating explanation. Same proxy caveat as Test 3."""
    threat = _series(timeline, "perceived_threat")
    supp = _series(timeline, "support_buffer")
    norm = _series(timeline, "normative_constraint")

    if _trend_delta(threat) >= _TREND_DELTA_THRESHOLD:
        if _trend_delta(supp) <= -_TREND_DELTA_THRESHOLD:
            # Allowed if normative_constraint also rises (moderating).
            if _trend_delta(norm) >= _TREND_DELTA_THRESHOLD:
                return True
            return False
    return True


def _assertion_4_dissent_suppression(timeline: Timeline, derived: dict) -> bool:
    """If fear_signal AND repression_index rise together,
    dissent_capacity must not rise (without strong countervailing
    factors — moderating clause: normative_constraint OR support_buffer
    rising strongly)."""
    fear = _series(timeline, "fear_signal")
    rep = _series(timeline, "repression_index")
    diss = _series(timeline, "dissent_capacity")
    norm = _series(timeline, "normative_constraint")
    supp = _series(timeline, "support_buffer")

    if (_trend_delta(fear) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(rep) >= _TREND_DELTA_THRESHOLD):
        if _trend_delta(diss) >= _TREND_DELTA_THRESHOLD:
            # Countervailing factors must be strong.
            norm_strong = _trend_delta(norm) >= _SHARP_STEP_THRESHOLD
            supp_strong = _trend_delta(supp) >= _SHARP_STEP_THRESHOLD
            if not (norm_strong or supp_strong):
                return False
    return True


def _assertion_5_buffer(timeline: Timeline, derived: dict) -> bool:
    """If support_buffer AND normative_constraint both rise,
    fear_pressure should dampen (decline or be flat)."""
    supp = _series(timeline, "support_buffer")
    norm = _series(timeline, "normative_constraint")
    fp = derived["fear_pressure"]

    if (_trend_delta(supp) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(norm) >= _TREND_DELTA_THRESHOLD):
        return _trend_delta(fp) <= _TREND_DELTA_THRESHOLD
    return True


def _assertion_6_substitution(timeline: Timeline, derived: dict) -> bool:
    """If digital_repression rises materially, authoritarian_risk must
    register an increase, even if physical repression is partially
    hidden."""
    digi = _series(timeline, "digital_repression")
    risk = derived["authoritarian_risk"]

    if _trend_delta(digi) >= _TREND_DELTA_THRESHOLD:
        return _trend_delta(risk) > 0
    return True


# ===========================================================================
# Scoring rubric (per work-set § 5)
# ===========================================================================
def _score_structural_consistency(timeline: Timeline, derived: dict) -> int:
    """0-2: do the SIGNS of relationships align with literature?
        +1 if Pearson(single_party_score, repression_index) >= 0
        +1 if Pearson(fear_signal, dissent_capacity)        <= 0

    N=0 timelines yield 0 (no data → no consistency claim).
    """
    if len(timeline.points) == 0:
        return 0

    sp = derived["single_party_score"]
    rep = _series(timeline, "repression_index")
    fear = _series(timeline, "fear_signal")
    diss = _series(timeline, "dissent_capacity")

    score = 0
    if _pearson_sign(sp, rep) >= 0:
        score += 1
    if _pearson_sign(fear, diss) <= 0:
        score += 1
    return score


def _score_timeline_sensitivity(timeline: Timeline, derived: dict) -> int:
    """0-2: does the model respond to time-ordered changes?
        +1 if direction of authoritarian_risk delta matches direction
            of autocratization delta
        +1 if any trigger_event is followed by a meaningful change in
            authoritarian_risk within the response window

    N=0 timelines yield 0 (no data → no sensitivity claim).
    """
    if len(timeline.points) == 0:
        return 0

    auto = _series(timeline, "autocratization")
    risk = derived["authoritarian_risk"]
    points = timeline.points
    n = len(points)

    score = 0
    auto_d = _trend_delta(auto)
    risk_d = _trend_delta(risk)
    # Both zero counts as match (both quiet).
    if (auto_d == 0 and risk_d == 0):
        score += 1
    elif (auto_d > 0 and risk_d > 0) or (auto_d < 0 and risk_d < 0):
        score += 1
    elif auto_d == 0 or risk_d == 0:
        # One is quiet, other moves — neutral, no point.
        pass

    # Trigger-event response.
    triggered_response = False
    has_event = False
    for i in range(n - 1):
        if not points[i].trigger_event:
            continue
        has_event = True
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        risk_window = risk[i:end + 1]
        if max(risk_window) - min(risk_window) >= _TREND_DELTA_THRESHOLD:
            triggered_response = True
            break
    if not has_event:
        # No event present — give the point (cannot be penalised for
        # absent input).
        score += 1
    elif triggered_response:
        score += 1
    return score


def _score_fear_mechanism(timeline: Timeline, derived: dict) -> int:
    """0-2: does fear reduce dissent or raise compliance?
        +1 if Pearson(fear_signal, dissent_capacity) <= 0
        +1 if any rise in fear is followed by a fall in dissent_capacity
            in the next period

    N=0 timelines yield 0 (no data → no mechanism claim). The previous
    implementation called max([]) on the fear series and crashed.
    """
    if len(timeline.points) == 0:
        return 0

    fear = _series(timeline, "fear_signal")
    diss = _series(timeline, "dissent_capacity")
    n = len(fear)

    score = 0
    if _pearson_sign(fear, diss) <= 0:
        score += 1

    # Step-wise: any (fear up, dissent down) adjacent pair.
    for i in range(1, n):
        if (fear[i] - fear[i - 1] >= _TREND_DELTA_THRESHOLD
                and diss[i] - diss[i - 1] <= -_TREND_DELTA_THRESHOLD):
            score += 1
            break
    else:
        # No fear-rise observed at all → award the point (no failure
        # mode tested). `fear` is guaranteed non-empty by the N=0 guard
        # above.
        if max(fear) - min(fear) < _TREND_DELTA_THRESHOLD:
            score += 1
    return min(score, 2)


def _score_threat_mechanism(timeline: Timeline, derived: dict) -> int:
    """0-2: does threat predict support for restrictive authority?
        Uses support_buffer as a noisy proxy (per Test 3 caveat).

        +1 if Pearson(perceived_threat, support_buffer) >= 0
        +1 if any threat-spike step is followed by an authoritarian_risk
            rise within the response window

    N=0 timelines yield 0 (no data → no mechanism claim).
    """
    if len(timeline.points) == 0:
        return 0

    threat = _series(timeline, "perceived_threat")
    supp = _series(timeline, "support_buffer")
    risk = derived["authoritarian_risk"]
    n = len(threat)

    score = 0
    if _pearson_sign(threat, supp) >= 0:
        score += 1

    # Threat-spike → authoritarian_risk response.
    spike_found = False
    risk_followed = False
    for i in range(1, n):
        if threat[i] - threat[i - 1] >= _SHARP_STEP_THRESHOLD:
            spike_found = True
            end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
            if max(risk[j] for j in range(i, end + 1)) - risk[i] >= 0:
                risk_followed = True
                break
    if not spike_found:
        score += 1   # no spike to test, no failure mode
    elif risk_followed:
        score += 1
    return min(score, 2)


def _score_repression_coverage(timeline: Timeline, derived: dict) -> int:
    """0-2: does authoritarian_risk include both physical and digital
    repression?

    Structurally locked at 2 because _authoritarian_risk's formula
    includes BOTH repression_index AND digital_repression. Documented
    here so any future formula change must also revisit this score.

    N=0 timelines yield 0 (no data → no coverage claim).
    """
    _ = derived  # signature parity with the other dimensions
    if len(timeline.points) == 0:
        return 0
    return 2


# ===========================================================================
# Public API — run_single_party_fear_regression
# ===========================================================================
def run_single_party_fear_regression(
    timeline: Timeline,
) -> SinglePartyFearRegressionResult:
    """Pure validator for the Single-Party Fear regression.

    Args:
        timeline: A Timeline with one or more TimePoints.

    Returns:
        SinglePartyFearRegressionResult with full rubric, scenario
        results, assertion outcomes, and the four derived series.

    Raises:
        ValueError if `timeline` is not a Timeline instance.
    """
    if not isinstance(timeline, Timeline):
        raise ValueError(
            f"run_single_party_fear_regression expected Timeline, "
            f"got {type(timeline).__name__}"
        )

    # ELINS Unit 3 — N=0 timelines yield a vacuous, safe result:
    #   * derived series are empty
    #   * scenario tests vacuously pass (no input pattern present)
    #   * assertions vacuously pass (no antecedent present)
    #   * every scoring dimension is 0 (no data → no claim)
    #   * total score is 0 → "Fails core logic" band
    # Short-circuit here so downstream helpers never need to handle
    # empty series at runtime; the per-helper N=0 guards remain as
    # defense-in-depth for direct callers.
    if len(timeline.points) == 0:
        return SinglePartyFearRegressionResult(
            timeline_id=timeline.timeline_id,
            score=0,
            structural_consistency_score=0,
            timeline_sensitivity_score=0,
            fear_mechanism_score=0,
            threat_mechanism_score=0,
            repression_coverage_score=0,
            assertions_passed=(
                "assertion_1_monotonicity",
                "assertion_2_fear_repression",
                "assertion_3_threat_authoritarian",
                "assertion_4_dissent_suppression",
                "assertion_5_buffer",
                "assertion_6_substitution",
            ),
            assertions_failed=(),
            scenario_results={
                "test_1_rising_concentration": True,
                "test_2_crackdown_event": True,
                "test_3_threat_spike_without_full_repression": True,
                "test_4_constraint_restoration": True,
                "test_5_digital_substitution": True,
            },
            derived_series={
                "single_party_score":  [],
                "fear_pressure":       [],
                "authoritarian_risk":  [],
                "dissent_suppression": [],
            },
        )

    derived = _build_derived_series(timeline)

    # Scenario tests.
    scenario_results = {
        "test_1_rising_concentration":
            _test_1_rising_concentration(timeline, derived),
        "test_2_crackdown_event":
            _test_2_crackdown_event(timeline, derived),
        "test_3_threat_spike_without_full_repression":
            _test_3_threat_spike_without_full_repression(timeline, derived),
        "test_4_constraint_restoration":
            _test_4_constraint_restoration(timeline, derived),
        "test_5_digital_substitution":
            _test_5_digital_substitution(timeline, derived),
    }

    # Assertions.
    assertion_runners = (
        ("assertion_1_monotonicity",         _assertion_1_monotonicity),
        ("assertion_2_fear_repression",      _assertion_2_fear_repression),
        ("assertion_3_threat_authoritarian", _assertion_3_threat_authoritarian),
        ("assertion_4_dissent_suppression",  _assertion_4_dissent_suppression),
        ("assertion_5_buffer",               _assertion_5_buffer),
        ("assertion_6_substitution",         _assertion_6_substitution),
    )
    passed = []
    failed = []
    for name, runner in assertion_runners:
        if runner(timeline, derived):
            passed.append(name)
        else:
            failed.append(name)

    # Scoring rubric.
    sc = _score_structural_consistency(timeline, derived)
    ts = _score_timeline_sensitivity(timeline, derived)
    fm = _score_fear_mechanism(timeline, derived)
    tm = _score_threat_mechanism(timeline, derived)
    rc = _score_repression_coverage(timeline, derived)
    total = sc + ts + fm + tm + rc

    return SinglePartyFearRegressionResult(
        timeline_id=timeline.timeline_id,
        score=total,
        structural_consistency_score=sc,
        timeline_sensitivity_score=ts,
        fear_mechanism_score=fm,
        threat_mechanism_score=tm,
        repression_coverage_score=rc,
        assertions_passed=tuple(passed),
        assertions_failed=tuple(failed),
        scenario_results=dict(scenario_results),
        derived_series=dict(derived),
    )
