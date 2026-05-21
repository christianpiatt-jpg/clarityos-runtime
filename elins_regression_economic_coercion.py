"""
elins_regression_economic_coercion.py — ELINS Unit 4.

Callable validation harness for the "Economic Coercion and Compliance
Across Timelines" regression. Pure, deterministic, side-effect-free.
Parallel in shape to ELINS Unit 1 (single-party fear), but operating in
the political-economy domain.

ROLE
----
Post-inference validator, NOT a predictor.

Given a TimelineEconomic of TimePointEconomic carrying structural
economic-coercion variables (economic_pressure, material_insecurity,
state_coercion, compliance_signal, resistance_capacity, support_buffer),
the validator:
    1. Computes four derived series (coercion_pressure, compliance_risk,
       shock_index, buffer_adjusted_pressure).
    2. Evaluates five scenario tests (rising coercion, economic shock
       event, buffer intervention, coercion substitution, shock without
       coercion).
    3. Evaluates six structural assertions over the derived series.
    4. Produces an EconomicCoercionRegressionResult — a 0-10 score plus
       per-test / per-assertion booleans plus the four derived series.

Does NOT:
    * predict, generate, or forecast timelines
    * make normative or political judgments
    * call any I/O / LLM / network
    * mutate the input timeline
    * import or modify Unit 1 / Unit 2 modules

PUBLIC API
----------
    run_economic_coercion_regression(timeline) -> EconomicCoercionRegressionResult

WEIGHTING SCHEME (locked, equal weights)
SCORING RUBRIC (locked, 0-2 per dimension × 5 dimensions = 0-10)
N=0 BEHAVIOR (Unit 3 convention): vacuous safe result, score 0.

See ELINS Unit 4 work-set for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


# ===========================================================================
# Locked constants
# ===========================================================================
_TREND_DELTA_THRESHOLD: float = 0.10
_SHARP_STEP_THRESHOLD: float = 0.30
_EVENT_RESPONSE_WINDOW: int = 3
_NEAR_MONOTONIC_TOLERANCE: float = 0.20
_MODEST_DELTA_THRESHOLD: float = 0.15
_FLAT_TOLERANCE: float = 0.05  # |delta| <= this counts as "flat"

# Equal weights for the two-input compliance-risk index.
_COMPLIANCE_RISK_WEIGHTS: tuple = (1.0, 1.0)

# Scoring thresholds (parallel to Unit 1).
SCORE_STRONG_FLOOR: int = 9
SCORE_ACCEPTABLE_FLOOR: int = 7
SCORE_WEAK_FLOOR: int = 5


# ===========================================================================
# Schemas — frozen dataclasses
# ===========================================================================
@dataclass(frozen=True)
class TimePointEconomic:
    """One time point in an economic-coercion regression timeline.

    All structural variables live in [0.0, 1.0] (the validator does not
    enforce this — out-of-range values are scored naturally).
    """
    t:                    str
    economic_pressure:    float
    material_insecurity:  float
    state_coercion:       float
    compliance_signal:    float
    resistance_capacity:  float
    support_buffer:       float
    trigger_event:        Optional[str] = None


@dataclass(frozen=True)
class TimelineEconomic:
    """An economic-coercion regression timeline. `points[0]` is earliest."""
    timeline_id: str
    points:      tuple   # tuple[TimePointEconomic, ...]


@dataclass(frozen=True)
class EconomicCoercionRegressionResult:
    """Validation verdict for a TimelineEconomic.

    Carries the locked rubric dimensions, per-assertion + per-scenario
    booleans, and the four derived series for downstream inspection.
    """
    timeline_id:                  str
    score:                        int   # 0-10
    structural_consistency_score: int   # 0-2
    timeline_sensitivity_score:   int   # 0-2
    coercion_mechanism_score:     int   # 0-2
    shock_mechanism_score:        int   # 0-2
    buffer_mechanism_score:       int   # 0-2
    assertions_passed:            tuple
    assertions_failed:            tuple
    scenario_results:             dict
    derived_series:               dict


# ===========================================================================
# Helpers — series math (parallel to Unit 1; intentionally duplicated to
# keep the modules independent so changes in one cannot regress the other)
# ===========================================================================
def _series(timeline: TimelineEconomic, attr: str) -> list:
    return [getattr(p, attr) for p in timeline.points]


def _mean(xs: Sequence[float]) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    return sum(xs) / n


def _weighted_mean(xs: Sequence[float], weights: Sequence[float]) -> float:
    if not xs:
        return 0.0
    total_weight = sum(weights)
    if total_weight == 0.0:
        return 0.0
    return sum(x * w for x, w in zip(xs, weights)) / total_weight


def _trend_delta(series: list) -> float:
    if len(series) < 2:
        return 0.0
    return series[-1] - series[0]


def _max_step_drop(series: list) -> float:
    if len(series) < 2:
        return 0.0
    max_drop = 0.0
    for i in range(1, len(series)):
        drop = series[i - 1] - series[i]
        if drop > max_drop:
            max_drop = drop
    return max_drop


def _pearson_sign(xs: list, ys: list) -> int:
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
# Derived variables (per work-set § 3)
# ===========================================================================
def _coercion_pressure_at(p: TimePointEconomic) -> float:
    """Mean of (economic_pressure, material_insecurity, state_coercion)."""
    return _mean((p.economic_pressure, p.material_insecurity, p.state_coercion))


def _compliance_risk_at(p: TimePointEconomic) -> float:
    """Equal-weight mean of (coercion_pressure, 1 - resistance_capacity)."""
    return _weighted_mean(
        (_coercion_pressure_at(p), 1.0 - p.resistance_capacity),
        _COMPLIANCE_RISK_WEIGHTS,
    )


def _buffer_adjusted_pressure_at(p: TimePointEconomic) -> float:
    """coercion_pressure × (1 - support_buffer)."""
    return _coercion_pressure_at(p) * (1.0 - p.support_buffer)


def _shock_index_series(timeline: TimelineEconomic) -> list:
    """Per-point step change averaging economic_pressure delta and
    material_insecurity delta. Index 0 is 0.0 (no prior point)."""
    points = timeline.points
    n = len(points)
    if n == 0:
        return []
    out: list = [0.0]
    for i in range(1, n):
        ep_delta = points[i].economic_pressure - points[i - 1].economic_pressure
        mi_delta = points[i].material_insecurity - points[i - 1].material_insecurity
        out.append(_mean((ep_delta, mi_delta)))
    return out


def _build_derived_series(timeline: TimelineEconomic) -> dict:
    return {
        "coercion_pressure":         [_coercion_pressure_at(p) for p in timeline.points],
        "compliance_risk":           [_compliance_risk_at(p)   for p in timeline.points],
        "shock_index":               _shock_index_series(timeline),
        "buffer_adjusted_pressure":  [_buffer_adjusted_pressure_at(p) for p in timeline.points],
    }


# ===========================================================================
# Scenario tests (per work-set § 4)
# ===========================================================================

def _test_1_rising_coercion(timeline: TimelineEconomic, derived: dict) -> bool:
    """Pattern: economic_pressure ↑ AND material_insecurity ↑.
    Pass: compliance_risk does not fall (delta >= 0)."""
    ep = _series(timeline, "economic_pressure")
    mi = _series(timeline, "material_insecurity")
    risk = derived["compliance_risk"]

    if (_trend_delta(ep) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(mi) >= _TREND_DELTA_THRESHOLD):
        return _trend_delta(risk) >= 0
    return True


def _test_2_economic_shock_event(timeline: TimelineEconomic, derived: dict) -> bool:
    """Pattern: trigger_event followed by sharp shock_index spike.
    Pass: compliance_signal rises OR resistance_capacity falls in window."""
    points = timeline.points
    n = len(points)
    shock = derived["shock_index"]
    comp = _series(timeline, "compliance_signal")
    resi = _series(timeline, "resistance_capacity")

    for i in range(n - 1):
        if not points[i].trigger_event:
            continue
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        max_shock = max(shock[j] for j in range(i + 1, end + 1))
        if max_shock < _SHARP_STEP_THRESHOLD:
            continue
        comp_rise = max(comp[j] for j in range(i + 1, end + 1)) - comp[i]
        resi_fall = resi[i] - min(resi[j] for j in range(i + 1, end + 1))
        if (comp_rise < _TREND_DELTA_THRESHOLD
                and resi_fall < _TREND_DELTA_THRESHOLD):
            return False
    return True


def _test_3_buffer_intervention(timeline: TimelineEconomic, derived: dict) -> bool:
    """Pattern: support_buffer ↑.
    Pass: buffer_adjusted_pressure should fall (delta <= 0)."""
    supp = _series(timeline, "support_buffer")
    bap = derived["buffer_adjusted_pressure"]

    if _trend_delta(supp) >= _TREND_DELTA_THRESHOLD:
        return _trend_delta(bap) <= 0
    return True


def _test_4_coercion_substitution(timeline: TimelineEconomic, derived: dict) -> bool:
    """Pattern: state_coercion ↑ while economic_pressure flat (|delta| <= flat tol).
    Pass: compliance_risk still rises."""
    sc = _series(timeline, "state_coercion")
    ep = _series(timeline, "economic_pressure")
    risk = derived["compliance_risk"]

    if (_trend_delta(sc) >= _TREND_DELTA_THRESHOLD
            and abs(_trend_delta(ep)) <= _FLAT_TOLERANCE):
        return _trend_delta(risk) > 0
    return True


def _test_5_shock_without_coercion(timeline: TimelineEconomic, derived: dict) -> bool:
    """Pattern: material_insecurity ↑ while state_coercion flat.
    Pass: compliance_signal may rise modestly but must not collapse
    (no sharp single-step drop)."""
    mi = _series(timeline, "material_insecurity")
    sc = _series(timeline, "state_coercion")
    comp = _series(timeline, "compliance_signal")

    if (_trend_delta(mi) >= _TREND_DELTA_THRESHOLD
            and abs(_trend_delta(sc)) <= _FLAT_TOLERANCE):
        # "not collapse" = no single-step drop exceeds the sharp threshold.
        return _max_step_drop(comp) < _SHARP_STEP_THRESHOLD
    return True


# ===========================================================================
# Assertions (per work-set § 5)
# ===========================================================================

def _assertion_1_coercion_pressure_monotonicity(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If coercion_pressure rises AND resistance_capacity does not rise
    sharply, compliance_risk must not decline."""
    cp = derived["coercion_pressure"]
    resi = _series(timeline, "resistance_capacity")
    risk = derived["compliance_risk"]

    if (_trend_delta(cp) >= _TREND_DELTA_THRESHOLD
            and _trend_delta(resi) < _SHARP_STEP_THRESHOLD):
        return _trend_delta(risk) >= 0
    return True


def _assertion_2_shock_compliance(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If shock_index rises sharply at any step, either compliance_signal
    must rise OR resistance_capacity must fall in the response window
    (unless support_buffer rises strongly to offset)."""
    points = timeline.points
    n = len(points)
    shock = derived["shock_index"]
    comp = _series(timeline, "compliance_signal")
    resi = _series(timeline, "resistance_capacity")
    supp = _series(timeline, "support_buffer")

    for i in range(1, n):
        if shock[i] < _SHARP_STEP_THRESHOLD:
            continue
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        comp_rise = max(comp[j] for j in range(i, end + 1)) - comp[i - 1]
        resi_fall = resi[i - 1] - min(resi[j] for j in range(i, end + 1))
        if (comp_rise >= _TREND_DELTA_THRESHOLD
                or resi_fall >= _TREND_DELTA_THRESHOLD):
            continue
        # Neither compliance rose nor resistance fell. Allowed only if
        # support_buffer rose strongly in the same window.
        supp_rise = (max(supp[j] for j in range(i, end + 1)) - supp[i - 1])
        if supp_rise < _TREND_DELTA_THRESHOLD:
            return False
    return True


def _assertion_3_buffer_dampening(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If support_buffer rises strongly while coercion_pressure does not
    decline, buffer_adjusted_pressure must end below its starting value."""
    supp = _series(timeline, "support_buffer")
    cp = derived["coercion_pressure"]
    bap = derived["buffer_adjusted_pressure"]

    if (_trend_delta(supp) >= _SHARP_STEP_THRESHOLD
            and _trend_delta(cp) >= 0):
        return _trend_delta(bap) <= 0
    return True


def _assertion_4_resistance_capacity(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If resistance_capacity rises strongly, compliance_signal must not
    rise (without strong coercion offset — coercion_pressure rising
    sharply allows compliance to rise even with stronger resistance)."""
    resi = _series(timeline, "resistance_capacity")
    comp = _series(timeline, "compliance_signal")
    cp = derived["coercion_pressure"]

    if _trend_delta(resi) >= _SHARP_STEP_THRESHOLD:
        if _trend_delta(comp) >= _TREND_DELTA_THRESHOLD:
            # Allowed only if coercion_pressure rose sharply too.
            if _trend_delta(cp) >= _SHARP_STEP_THRESHOLD:
                return True
            return False
    return True


def _assertion_5_substitution(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If state_coercion rises materially, compliance_risk must register
    an increase (even if economic_pressure is flat)."""
    sc = _series(timeline, "state_coercion")
    risk = derived["compliance_risk"]

    if _trend_delta(sc) >= _TREND_DELTA_THRESHOLD:
        return _trend_delta(risk) > 0
    return True


def _assertion_6_economic_pressure_compliance(
    timeline: TimelineEconomic, derived: dict,
) -> bool:
    """If economic_pressure rises sharply, compliance_signal must not
    fall sharply (no single-step drop exceeding the sharp threshold)."""
    ep = _series(timeline, "economic_pressure")
    comp = _series(timeline, "compliance_signal")

    if _trend_delta(ep) >= _SHARP_STEP_THRESHOLD:
        return _max_step_drop(comp) < _SHARP_STEP_THRESHOLD
    return True


# ===========================================================================
# Scoring rubric (per work-set § 6)
# ===========================================================================

def _score_structural_consistency(
    timeline: TimelineEconomic, derived: dict,
) -> int:
    """0-2:
        +1 if Pearson(coercion_pressure, compliance_signal) >= 0
        +1 if Pearson(resistance_capacity, compliance_signal) <= 0

    N=0 timelines yield 0.
    """
    if len(timeline.points) == 0:
        return 0

    cp = derived["coercion_pressure"]
    comp = _series(timeline, "compliance_signal")
    resi = _series(timeline, "resistance_capacity")

    score = 0
    if _pearson_sign(cp, comp) >= 0:
        score += 1
    if _pearson_sign(resi, comp) <= 0:
        score += 1
    return score


def _score_timeline_sensitivity(
    timeline: TimelineEconomic, derived: dict,
) -> int:
    """0-2:
        +1 if direction of compliance_risk delta matches direction of
            coercion_pressure delta
        +1 if any trigger_event is followed by a meaningful change in
            compliance_risk within the response window

    N=0 timelines yield 0.
    """
    if len(timeline.points) == 0:
        return 0

    cp = derived["coercion_pressure"]
    risk = derived["compliance_risk"]
    points = timeline.points
    n = len(points)

    score = 0
    cp_d = _trend_delta(cp)
    risk_d = _trend_delta(risk)
    if cp_d == 0 and risk_d == 0:
        score += 1
    elif (cp_d > 0 and risk_d > 0) or (cp_d < 0 and risk_d < 0):
        score += 1

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
        score += 1
    elif triggered_response:
        score += 1
    return score


def _score_coercion_mechanism(
    timeline: TimelineEconomic, derived: dict,
) -> int:
    """0-2:
        +1 if Pearson(coercion_pressure, compliance_risk) >= 0
        +1 if any rise in coercion_pressure is followed by a rise in
            compliance_signal within the response window (or no rise
            in coercion_pressure observed)

    N=0 timelines yield 0.
    """
    if len(timeline.points) == 0:
        return 0

    cp = derived["coercion_pressure"]
    comp = _series(timeline, "compliance_signal")
    n = len(cp)

    score = 0
    if _pearson_sign(cp, _series(timeline, "compliance_risk_proxy") if False
                     else derived["compliance_risk"]) >= 0:
        score += 1

    # Step-wise: any (cp up, comp up) adjacent pair within window.
    saw_cp_rise = False
    matched = False
    for i in range(1, n):
        if cp[i] - cp[i - 1] >= _TREND_DELTA_THRESHOLD:
            saw_cp_rise = True
            end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
            if max(comp[j] for j in range(i, end + 1)) - comp[i - 1] >= _TREND_DELTA_THRESHOLD:
                matched = True
                break
    if not saw_cp_rise:
        score += 1   # no rise to test, no failure mode
    elif matched:
        score += 1
    return min(score, 2)


def _score_shock_mechanism(
    timeline: TimelineEconomic, derived: dict,
) -> int:
    """0-2:
        +1 if Pearson(shock_index, compliance_signal) >= 0
        +1 if any sharp shock step is followed by compliance rise OR
            resistance fall within the response window (or no sharp
            shock observed)

    N=0 timelines yield 0.
    """
    if len(timeline.points) == 0:
        return 0

    shock = derived["shock_index"]
    comp = _series(timeline, "compliance_signal")
    resi = _series(timeline, "resistance_capacity")
    n = len(shock)

    score = 0
    if _pearson_sign(shock, comp) >= 0:
        score += 1

    saw_sharp = False
    matched = False
    for i in range(1, n):
        if shock[i] < _SHARP_STEP_THRESHOLD:
            continue
        saw_sharp = True
        end = min(n - 1, i + _EVENT_RESPONSE_WINDOW)
        comp_rise = max(comp[j] for j in range(i, end + 1)) - comp[i - 1]
        resi_fall = resi[i - 1] - min(resi[j] for j in range(i, end + 1))
        if (comp_rise >= _TREND_DELTA_THRESHOLD
                or resi_fall >= _TREND_DELTA_THRESHOLD):
            matched = True
            break
    if not saw_sharp:
        score += 1
    elif matched:
        score += 1
    return min(score, 2)


def _score_buffer_mechanism(
    timeline: TimelineEconomic, derived: dict,
) -> int:
    """0-2:
        +1 if Pearson(support_buffer, buffer_adjusted_pressure) <= 0
        +1 if support_buffer rising strongly implies buffer_adjusted_pressure
            falls (or no strong buffer rise observed)

    N=0 timelines yield 0.
    """
    if len(timeline.points) == 0:
        return 0

    supp = _series(timeline, "support_buffer")
    bap = derived["buffer_adjusted_pressure"]

    score = 0
    if _pearson_sign(supp, bap) <= 0:
        score += 1

    if _trend_delta(supp) >= _SHARP_STEP_THRESHOLD:
        if _trend_delta(bap) <= 0:
            score += 1
    else:
        # No strong buffer rise observed → no failure mode → award point.
        score += 1
    return min(score, 2)


# ===========================================================================
# Public API — run_economic_coercion_regression
# ===========================================================================
def run_economic_coercion_regression(
    timeline: TimelineEconomic,
) -> EconomicCoercionRegressionResult:
    """Pure validator for the Economic Coercion regression.

    Args:
        timeline: A TimelineEconomic with one or more TimePointEconomic.

    Returns:
        EconomicCoercionRegressionResult with full rubric, scenario
        results, assertion outcomes, and the four derived series.

    Raises:
        ValueError if `timeline` is not a TimelineEconomic instance.

    N=0 BEHAVIOR (Unit 3 convention):
        Empty timelines short-circuit to the vacuous result:
        score 0, all dimensions 0, all assertions vacuously pass,
        all scenarios vacuously pass, all derived series empty.
    """
    if not isinstance(timeline, TimelineEconomic):
        raise ValueError(
            f"run_economic_coercion_regression expected TimelineEconomic, "
            f"got {type(timeline).__name__}"
        )

    if len(timeline.points) == 0:
        return EconomicCoercionRegressionResult(
            timeline_id=timeline.timeline_id,
            score=0,
            structural_consistency_score=0,
            timeline_sensitivity_score=0,
            coercion_mechanism_score=0,
            shock_mechanism_score=0,
            buffer_mechanism_score=0,
            assertions_passed=(
                "assertion_1_coercion_pressure_monotonicity",
                "assertion_2_shock_compliance",
                "assertion_3_buffer_dampening",
                "assertion_4_resistance_capacity",
                "assertion_5_substitution",
                "assertion_6_economic_pressure_compliance",
            ),
            assertions_failed=(),
            scenario_results={
                "test_1_rising_coercion":         True,
                "test_2_economic_shock_event":    True,
                "test_3_buffer_intervention":     True,
                "test_4_coercion_substitution":   True,
                "test_5_shock_without_coercion":  True,
            },
            derived_series={
                "coercion_pressure":         [],
                "compliance_risk":           [],
                "shock_index":               [],
                "buffer_adjusted_pressure":  [],
            },
        )

    derived = _build_derived_series(timeline)

    scenario_results = {
        "test_1_rising_coercion":
            _test_1_rising_coercion(timeline, derived),
        "test_2_economic_shock_event":
            _test_2_economic_shock_event(timeline, derived),
        "test_3_buffer_intervention":
            _test_3_buffer_intervention(timeline, derived),
        "test_4_coercion_substitution":
            _test_4_coercion_substitution(timeline, derived),
        "test_5_shock_without_coercion":
            _test_5_shock_without_coercion(timeline, derived),
    }

    assertion_runners = (
        ("assertion_1_coercion_pressure_monotonicity",
         _assertion_1_coercion_pressure_monotonicity),
        ("assertion_2_shock_compliance",
         _assertion_2_shock_compliance),
        ("assertion_3_buffer_dampening",
         _assertion_3_buffer_dampening),
        ("assertion_4_resistance_capacity",
         _assertion_4_resistance_capacity),
        ("assertion_5_substitution",
         _assertion_5_substitution),
        ("assertion_6_economic_pressure_compliance",
         _assertion_6_economic_pressure_compliance),
    )
    passed = []
    failed = []
    for name, runner in assertion_runners:
        if runner(timeline, derived):
            passed.append(name)
        else:
            failed.append(name)

    sc = _score_structural_consistency(timeline, derived)
    ts = _score_timeline_sensitivity(timeline, derived)
    cm = _score_coercion_mechanism(timeline, derived)
    sm = _score_shock_mechanism(timeline, derived)
    bm = _score_buffer_mechanism(timeline, derived)
    total = sc + ts + cm + sm + bm

    return EconomicCoercionRegressionResult(
        timeline_id=timeline.timeline_id,
        score=total,
        structural_consistency_score=sc,
        timeline_sensitivity_score=ts,
        coercion_mechanism_score=cm,
        shock_mechanism_score=sm,
        buffer_mechanism_score=bm,
        assertions_passed=tuple(passed),
        assertions_failed=tuple(failed),
        scenario_results=dict(scenario_results),
        derived_series=dict(derived),
    )
