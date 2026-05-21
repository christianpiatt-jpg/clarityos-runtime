"""
Tests for ELINS Unit 4 — Economic Coercion regression validator,
wrapper, and FastAPI endpoint.

Layered coverage (≥ 80 tests):
    A. Schemas — frozen + instantiable
    B. Helper math — mean / weighted_mean / trend_delta / pearson_sign
    C. Derived variables — 4 functions
    D. Scenario tests — 5 scenarios, positive + negative + vacuous
    E. Assertions — 6 assertions, pass + fail + vacuous
    F. Scoring — each dimension + total boundaries + locked thresholds
    G. N=0 (Unit 3 convention) — empty-timeline behavior + helper safety
    H. Determinism + purity (no mutation, no side effects)
    I. Source-code purity
    J. Wrapper — get_economic_coercion_regression
    K. Endpoint — /elins/regression/economic_coercion
    L. Isolation — does not import basin inference modules
    M. Independence from Unit 1 module
    N. End-to-end smoke
"""
from __future__ import annotations

import inspect
import secrets
import time
from dataclasses import FrozenInstanceError

import pytest
from conftest import TestClient

import elins_regression_economic_coercion as ec
import elins_timeline_dashboard as etd
from elins_regression_economic_coercion import (
    EconomicCoercionRegressionResult,
    TimelineEconomic,
    TimePointEconomic,
    run_economic_coercion_regression,
)


# ===========================================================================
# Fixture builders
# ===========================================================================
def _tp(
    *,
    t: str = "t0",
    economic_pressure: float = 0.5,
    material_insecurity: float = 0.5,
    state_coercion: float = 0.5,
    compliance_signal: float = 0.5,
    resistance_capacity: float = 0.5,
    support_buffer: float = 0.5,
    trigger_event=None,
) -> TimePointEconomic:
    return TimePointEconomic(
        t=t,
        economic_pressure=economic_pressure,
        material_insecurity=material_insecurity,
        state_coercion=state_coercion,
        compliance_signal=compliance_signal,
        resistance_capacity=resistance_capacity,
        support_buffer=support_buffer,
        trigger_event=trigger_event,
    )


def _flat_timeline(n: int = 4) -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id="flat",
        points=tuple(_tp(t=f"t{i}") for i in range(n)),
    )


def _rising_coercion_timeline() -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id="rising_coercion",
        points=(
            _tp(t="t0", economic_pressure=0.2, material_insecurity=0.2,
                state_coercion=0.2, compliance_signal=0.2,
                resistance_capacity=0.7, support_buffer=0.7),
            _tp(t="t1", economic_pressure=0.5, material_insecurity=0.5,
                state_coercion=0.5, compliance_signal=0.4,
                resistance_capacity=0.5, support_buffer=0.5,
                trigger_event="layoffs"),
            _tp(t="t2", economic_pressure=0.8, material_insecurity=0.8,
                state_coercion=0.7, compliance_signal=0.6,
                resistance_capacity=0.3, support_buffer=0.3),
        ),
    )


def _payload_from_timeline(tl: TimelineEconomic) -> dict:
    return {
        "timeline_id": tl.timeline_id,
        "points": [
            {
                "t": p.t,
                "economic_pressure":   p.economic_pressure,
                "material_insecurity": p.material_insecurity,
                "state_coercion":      p.state_coercion,
                "compliance_signal":   p.compliance_signal,
                "resistance_capacity": p.resistance_capacity,
                "support_buffer":      p.support_buffer,
                "trigger_event":       p.trigger_event,
            }
            for p in tl.points
        ],
    }


# ===========================================================================
# A. Schemas
# ===========================================================================
class TestSchemas:
    def test_timepoint_instantiable(self):
        assert _tp().economic_pressure == 0.5

    def test_timepoint_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _tp().economic_pressure = 0.9  # type: ignore[misc]

    def test_timepoint_default_trigger_event_none(self):
        assert _tp().trigger_event is None

    def test_timeline_instantiable(self):
        tl = _flat_timeline(n=2)
        assert tl.timeline_id == "flat"
        assert len(tl.points) == 2

    def test_timeline_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _flat_timeline(n=2).timeline_id = "x"  # type: ignore[misc]

    def test_result_instantiable(self):
        r = EconomicCoercionRegressionResult(
            timeline_id="x", score=10,
            structural_consistency_score=2,
            timeline_sensitivity_score=2,
            coercion_mechanism_score=2,
            shock_mechanism_score=2,
            buffer_mechanism_score=2,
            assertions_passed=(), assertions_failed=(),
            scenario_results={}, derived_series={},
        )
        assert r.score == 10

    def test_result_frozen(self):
        r = EconomicCoercionRegressionResult(
            timeline_id="x", score=0,
            structural_consistency_score=0,
            timeline_sensitivity_score=0,
            coercion_mechanism_score=0,
            shock_mechanism_score=0,
            buffer_mechanism_score=0,
            assertions_passed=(), assertions_failed=(),
            scenario_results={}, derived_series={},
        )
        with pytest.raises(FrozenInstanceError):
            r.score = 5  # type: ignore[misc]


# ===========================================================================
# B. Helper math
# ===========================================================================
class TestHelperMath:
    def test_mean_basic(self):
        assert ec._mean((1.0, 2.0, 3.0)) == 2.0

    def test_mean_empty(self):
        assert ec._mean(()) == 0.0

    def test_weighted_mean_equal(self):
        assert ec._weighted_mean((1.0, 3.0), (1.0, 1.0)) == 2.0

    def test_weighted_mean_zero_weights(self):
        assert ec._weighted_mean((1.0, 2.0), (0.0, 0.0)) == 0.0

    def test_trend_delta_increasing(self):
        assert ec._trend_delta([0.1, 0.5, 0.9]) == pytest.approx(0.8)

    def test_trend_delta_decreasing(self):
        assert ec._trend_delta([0.9, 0.1]) == pytest.approx(-0.8)

    def test_trend_delta_empty(self):
        assert ec._trend_delta([]) == 0.0

    def test_max_step_drop(self):
        assert ec._max_step_drop([0.5, 0.2, 0.4]) == pytest.approx(0.3)

    def test_max_step_drop_no_drops(self):
        assert ec._max_step_drop([0.1, 0.5, 0.9]) == 0.0

    def test_pearson_sign_positive(self):
        assert ec._pearson_sign([1, 2, 3], [10, 20, 30]) == 1

    def test_pearson_sign_negative(self):
        assert ec._pearson_sign([1, 2, 3], [30, 20, 10]) == -1

    def test_pearson_sign_zero_variance(self):
        assert ec._pearson_sign([1, 1, 1], [1, 2, 3]) == 0

    def test_pearson_sign_too_short(self):
        assert ec._pearson_sign([1.0], [2.0]) == 0


# ===========================================================================
# C. Derived variables
# ===========================================================================
class TestDerivedVariables:
    def test_coercion_pressure_mean(self):
        p = _tp(economic_pressure=0.3, material_insecurity=0.6, state_coercion=0.9)
        assert ec._coercion_pressure_at(p) == pytest.approx(0.6)

    def test_coercion_pressure_zeros(self):
        p = _tp(economic_pressure=0.0, material_insecurity=0.0, state_coercion=0.0)
        assert ec._coercion_pressure_at(p) == 0.0

    def test_coercion_pressure_max(self):
        p = _tp(economic_pressure=1.0, material_insecurity=1.0, state_coercion=1.0)
        assert ec._coercion_pressure_at(p) == 1.0

    def test_compliance_risk_high_when_resistance_low(self):
        p = _tp(economic_pressure=1.0, material_insecurity=1.0,
                state_coercion=1.0, resistance_capacity=0.0)
        # cp = 1.0; (cp + (1 - 0)) / 2 = 1.0
        assert ec._compliance_risk_at(p) == 1.0

    def test_compliance_risk_low_when_resistance_high(self):
        p = _tp(economic_pressure=0.0, material_insecurity=0.0,
                state_coercion=0.0, resistance_capacity=1.0)
        # cp = 0; (0 + (1 - 1)) / 2 = 0
        assert ec._compliance_risk_at(p) == 0.0

    def test_buffer_adjusted_pressure(self):
        p = _tp(economic_pressure=1.0, material_insecurity=1.0,
                state_coercion=1.0, support_buffer=0.5)
        # cp = 1.0; bap = 1.0 * (1 - 0.5) = 0.5
        assert ec._buffer_adjusted_pressure_at(p) == 0.5

    def test_buffer_adjusted_pressure_full_buffer_zero(self):
        p = _tp(economic_pressure=1.0, support_buffer=1.0)
        assert ec._buffer_adjusted_pressure_at(p) == 0.0

    def test_shock_index_first_point_zero(self):
        tl = _rising_coercion_timeline()
        shock = ec._shock_index_series(tl)
        assert shock[0] == 0.0

    def test_shock_index_step_change(self):
        tl = _rising_coercion_timeline()
        shock = ec._shock_index_series(tl)
        # t1: ep delta = 0.5 - 0.2 = 0.3; mi delta = 0.5 - 0.2 = 0.3 → mean 0.3
        assert shock[1] == pytest.approx(0.3)

    def test_shock_index_empty_timeline(self):
        tl = TimelineEconomic(timeline_id="empty", points=())
        assert ec._shock_index_series(tl) == []

    def test_build_derived_series_keys(self):
        derived = ec._build_derived_series(_flat_timeline())
        assert set(derived.keys()) == {
            "coercion_pressure", "compliance_risk",
            "shock_index", "buffer_adjusted_pressure",
        }

    def test_build_derived_series_lengths_match(self):
        tl = _flat_timeline(n=5)
        derived = ec._build_derived_series(tl)
        for series in derived.values():
            assert len(series) == 5


# ===========================================================================
# D. Scenario tests
# ===========================================================================
class TestScenario1RisingCoercion:
    def test_pattern_present_passes(self):
        tl = _rising_coercion_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_1_rising_coercion(tl, derived) is True

    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_1_rising_coercion(tl, derived) is True

    def test_pattern_present_but_risk_falls_fails(self):
        # Engineer: ep + mi rise but resistance_capacity rises hard so
        # compliance_risk falls.
        tl = TimelineEconomic(
            timeline_id="bad",
            points=(
                _tp(t="t0", economic_pressure=0.2, material_insecurity=0.2,
                    state_coercion=0.5, resistance_capacity=0.0),
                _tp(t="t1", economic_pressure=0.8, material_insecurity=0.8,
                    state_coercion=0.0, resistance_capacity=1.0),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_1_rising_coercion(tl, derived) is False


class TestScenario2EconomicShockEvent:
    def test_pattern_present_passes(self):
        tl = _rising_coercion_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_2_economic_shock_event(tl, derived) is True

    def test_no_trigger_vacuously_passes(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_2_economic_shock_event(tl, derived) is True

    def test_trigger_with_no_shock_vacuously_passes(self):
        tl = TimelineEconomic(
            timeline_id="trigger_no_shock",
            points=(
                _tp(t="t0", trigger_event="layoffs",
                    economic_pressure=0.3, material_insecurity=0.3),
                _tp(t="t1", economic_pressure=0.32, material_insecurity=0.32),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_2_economic_shock_event(tl, derived) is True

    def test_shock_without_response_fails(self):
        tl = TimelineEconomic(
            timeline_id="bad_shock",
            points=(
                _tp(t="t0", trigger_event="sanctions",
                    economic_pressure=0.2, material_insecurity=0.2,
                    compliance_signal=0.5, resistance_capacity=0.5),
                _tp(t="t1",
                    economic_pressure=0.7, material_insecurity=0.7,  # shock
                    compliance_signal=0.5, resistance_capacity=0.5),
                _tp(t="t2",
                    economic_pressure=0.7, material_insecurity=0.7,
                    compliance_signal=0.5, resistance_capacity=0.5),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_2_economic_shock_event(tl, derived) is False


class TestScenario3BufferIntervention:
    def test_buffer_rises_pressure_falls_passes(self):
        tl = TimelineEconomic(
            timeline_id="buffer",
            points=(
                _tp(t="t0", support_buffer=0.2,
                    economic_pressure=0.6, material_insecurity=0.6,
                    state_coercion=0.6),
                _tp(t="t1", support_buffer=0.8,
                    economic_pressure=0.6, material_insecurity=0.6,
                    state_coercion=0.6),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_3_buffer_intervention(tl, derived) is True

    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_3_buffer_intervention(tl, derived) is True

    def test_buffer_rises_but_pressure_grows_fails(self):
        # Engineer: support_buffer rises but coercion grows so much that
        # buffer_adjusted_pressure rises despite the buffer.
        tl = TimelineEconomic(
            timeline_id="bad_buffer",
            points=(
                _tp(t="t0", support_buffer=0.2,
                    economic_pressure=0.1, material_insecurity=0.1,
                    state_coercion=0.1),
                _tp(t="t1", support_buffer=0.4,
                    economic_pressure=1.0, material_insecurity=1.0,
                    state_coercion=1.0),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_3_buffer_intervention(tl, derived) is False


class TestScenario4CoercionSubstitution:
    def test_state_coercion_rises_ep_flat_passes(self):
        tl = TimelineEconomic(
            timeline_id="substitution",
            points=(
                _tp(t="t0", state_coercion=0.2, economic_pressure=0.4,
                    material_insecurity=0.4, resistance_capacity=0.7),
                _tp(t="t1", state_coercion=0.7, economic_pressure=0.4,
                    material_insecurity=0.6, resistance_capacity=0.4),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_4_coercion_substitution(tl, derived) is True

    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_4_coercion_substitution(tl, derived) is True


class TestScenario5ShockWithoutCoercion:
    def test_pattern_present_compliance_modest_passes(self):
        tl = TimelineEconomic(
            timeline_id="shock_only",
            points=(
                _tp(t="t0", material_insecurity=0.2, state_coercion=0.5,
                    compliance_signal=0.5),
                _tp(t="t1", material_insecurity=0.7, state_coercion=0.5,
                    compliance_signal=0.55),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_5_shock_without_coercion(tl, derived) is True

    def test_pattern_present_compliance_collapses_fails(self):
        tl = TimelineEconomic(
            timeline_id="collapse",
            points=(
                _tp(t="t0", material_insecurity=0.2, state_coercion=0.5,
                    compliance_signal=0.8),
                _tp(t="t1", material_insecurity=0.7, state_coercion=0.5,
                    compliance_signal=0.3),  # sharp drop
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._test_5_shock_without_coercion(tl, derived) is False

    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._test_5_shock_without_coercion(tl, derived) is True


# ===========================================================================
# E. Assertions (sample positive + negative cases per assertion)
# ===========================================================================
class TestAssertions:
    def test_assertion_1_passes_on_rising_coercion(self):
        tl = _rising_coercion_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._assertion_1_coercion_pressure_monotonicity(tl, derived) is True

    def test_assertion_1_vacuous_when_flat(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._assertion_1_coercion_pressure_monotonicity(tl, derived) is True

    def test_assertion_2_passes_on_responsive_shock(self):
        tl = _rising_coercion_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._assertion_2_shock_compliance(tl, derived) is True

    def test_assertion_2_fails_on_unresponsive_shock(self):
        tl = TimelineEconomic(
            timeline_id="unresp",
            points=(
                _tp(t="t0", economic_pressure=0.2, material_insecurity=0.2,
                    compliance_signal=0.5, resistance_capacity=0.5,
                    support_buffer=0.5),
                _tp(t="t1", economic_pressure=0.7, material_insecurity=0.7,
                    compliance_signal=0.5, resistance_capacity=0.5,
                    support_buffer=0.5),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_2_shock_compliance(tl, derived) is False

    def test_assertion_3_passes_buffer_dampens(self):
        tl = TimelineEconomic(
            timeline_id="dampen",
            points=(
                _tp(t="t0", support_buffer=0.2,
                    economic_pressure=0.5, material_insecurity=0.5,
                    state_coercion=0.5),
                _tp(t="t1", support_buffer=0.7,
                    economic_pressure=0.5, material_insecurity=0.5,
                    state_coercion=0.5),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_3_buffer_dampening(tl, derived) is True

    def test_assertion_3_fails_buffer_does_not_dampen(self):
        tl = TimelineEconomic(
            timeline_id="bad_dampen",
            points=(
                _tp(t="t0", support_buffer=0.2,
                    economic_pressure=0.1, material_insecurity=0.1,
                    state_coercion=0.1),
                _tp(t="t1", support_buffer=0.6,
                    economic_pressure=1.0, material_insecurity=1.0,
                    state_coercion=1.0),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_3_buffer_dampening(tl, derived) is False

    def test_assertion_4_passes_resistance_compliance_falls(self):
        tl = TimelineEconomic(
            timeline_id="resist",
            points=(
                _tp(t="t0", resistance_capacity=0.2, compliance_signal=0.7),
                _tp(t="t1", resistance_capacity=0.7, compliance_signal=0.4),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_4_resistance_capacity(tl, derived) is True

    def test_assertion_4_fails_resistance_and_compliance_both_rise(self):
        tl = TimelineEconomic(
            timeline_id="bad_resist",
            points=(
                _tp(t="t0", resistance_capacity=0.2, compliance_signal=0.3,
                    economic_pressure=0.5, material_insecurity=0.5,
                    state_coercion=0.5),
                _tp(t="t1", resistance_capacity=0.7, compliance_signal=0.6,
                    economic_pressure=0.5, material_insecurity=0.5,
                    state_coercion=0.5),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_4_resistance_capacity(tl, derived) is False

    def test_assertion_5_passes_substitution(self):
        tl = TimelineEconomic(
            timeline_id="sub_pass",
            points=(
                _tp(t="t0", state_coercion=0.2, economic_pressure=0.4,
                    material_insecurity=0.4, resistance_capacity=0.7),
                _tp(t="t1", state_coercion=0.8, economic_pressure=0.4,
                    material_insecurity=0.6, resistance_capacity=0.3),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_5_substitution(tl, derived) is True

    def test_assertion_5_vacuous_when_no_state_coercion_rise(self):
        tl = _flat_timeline()
        derived = ec._build_derived_series(tl)
        assert ec._assertion_5_substitution(tl, derived) is True

    def test_assertion_6_passes_compliance_does_not_collapse(self):
        tl = TimelineEconomic(
            timeline_id="ep_passes",
            points=(
                _tp(t="t0", economic_pressure=0.2, compliance_signal=0.5),
                _tp(t="t1", economic_pressure=0.7, compliance_signal=0.55),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_6_economic_pressure_compliance(tl, derived) is True

    def test_assertion_6_fails_compliance_collapses(self):
        tl = TimelineEconomic(
            timeline_id="ep_collapse",
            points=(
                _tp(t="t0", economic_pressure=0.2, compliance_signal=0.8),
                _tp(t="t1", economic_pressure=0.7, compliance_signal=0.3),
            ),
        )
        derived = ec._build_derived_series(tl)
        assert ec._assertion_6_economic_pressure_compliance(tl, derived) is False


# ===========================================================================
# F. Scoring rubric
# ===========================================================================
class TestScoringDimensions:
    def test_each_dimension_in_range(self):
        tl = _rising_coercion_timeline()
        derived = ec._build_derived_series(tl)
        for fn in (
            ec._score_structural_consistency,
            ec._score_timeline_sensitivity,
            ec._score_coercion_mechanism,
            ec._score_shock_mechanism,
            ec._score_buffer_mechanism,
        ):
            score = fn(tl, derived)
            assert 0 <= score <= 2


class TestTotalScoreBoundaries:
    def test_rising_coercion_strong(self):
        r = run_economic_coercion_regression(_rising_coercion_timeline())
        assert r.score >= 9

    def test_flat_timeline_high_score(self):
        r = run_economic_coercion_regression(_flat_timeline())
        assert r.score >= 7

    def test_total_in_range(self):
        for tl in (_flat_timeline(), _rising_coercion_timeline()):
            r = run_economic_coercion_regression(tl)
            assert 0 <= r.score <= 10

    def test_score_is_sum_of_dimensions(self):
        r = run_economic_coercion_regression(_rising_coercion_timeline())
        expected = (r.structural_consistency_score
                    + r.timeline_sensitivity_score
                    + r.coercion_mechanism_score
                    + r.shock_mechanism_score
                    + r.buffer_mechanism_score)
        assert r.score == expected

    def test_thresholds_locked(self):
        assert ec.SCORE_STRONG_FLOOR == 9
        assert ec.SCORE_ACCEPTABLE_FLOOR == 7
        assert ec.SCORE_WEAK_FLOOR == 5


# ===========================================================================
# G. N=0 (Unit 3 convention)
# ===========================================================================
class TestN0Behavior:
    def _empty(self) -> TimelineEconomic:
        return TimelineEconomic(timeline_id="empty", points=())

    def test_returns_result(self):
        r = run_economic_coercion_regression(self._empty())
        assert isinstance(r, EconomicCoercionRegressionResult)

    def test_score_zero(self):
        assert run_economic_coercion_regression(self._empty()).score == 0

    def test_all_dimension_scores_zero(self):
        r = run_economic_coercion_regression(self._empty())
        assert r.structural_consistency_score == 0
        assert r.timeline_sensitivity_score == 0
        assert r.coercion_mechanism_score == 0
        assert r.shock_mechanism_score == 0
        assert r.buffer_mechanism_score == 0

    def test_assertions_failed_empty(self):
        assert run_economic_coercion_regression(self._empty()).assertions_failed == ()

    def test_all_six_assertions_passed(self):
        r = run_economic_coercion_regression(self._empty())
        assert set(r.assertions_passed) == {
            "assertion_1_coercion_pressure_monotonicity",
            "assertion_2_shock_compliance",
            "assertion_3_buffer_dampening",
            "assertion_4_resistance_capacity",
            "assertion_5_substitution",
            "assertion_6_economic_pressure_compliance",
        }

    def test_all_scenarios_pass_vacuously(self):
        r = run_economic_coercion_regression(self._empty())
        assert all(r.scenario_results.values())

    def test_all_derived_series_empty(self):
        r = run_economic_coercion_regression(self._empty())
        for k, s in r.derived_series.items():
            assert s == [], f"{k} should be empty list"

    def test_does_not_raise_on_empty(self):
        try:
            run_economic_coercion_regression(self._empty())
        except Exception as e:
            pytest.fail(f"empty timeline raised {type(e).__name__}: {e}")

    def test_helpers_safe_on_empty(self):
        empty = self._empty()
        derived = {
            "coercion_pressure": [], "compliance_risk": [],
            "shock_index": [], "buffer_adjusted_pressure": [],
        }
        for fn in (
            ec._score_structural_consistency,
            ec._score_timeline_sensitivity,
            ec._score_coercion_mechanism,
            ec._score_shock_mechanism,
            ec._score_buffer_mechanism,
        ):
            assert fn(empty, derived) == 0


# ===========================================================================
# H. Determinism + purity
# ===========================================================================
class TestDeterminismPurity:
    def test_byte_equal_repeated_calls(self):
        tl = _rising_coercion_timeline()
        r1 = run_economic_coercion_regression(tl)
        r2 = run_economic_coercion_regression(tl)
        assert r1 == r2

    def test_timeline_not_mutated(self):
        tl = _rising_coercion_timeline()
        before = tuple((p.t, p.economic_pressure, p.compliance_signal) for p in tl.points)
        run_economic_coercion_regression(tl)
        after = tuple((p.t, p.economic_pressure, p.compliance_signal) for p in tl.points)
        assert before == after


# ===========================================================================
# I. Source-code purity
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ec)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports(self):
        src = self._src()
        for forbidden in ("import urllib", "import http", "import requests",
                          "import socket", "from urllib", "from http",
                          "from requests"):
            assert forbidden not in src

    def test_no_io(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "json.load", "json.dump", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets"):
            assert forbidden not in src

    def test_no_logging(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src


# ===========================================================================
# J. Wrapper — get_economic_coercion_regression
# ===========================================================================
class TestWrapper:
    def test_returns_dict(self):
        out = etd.get_economic_coercion_regression(_rising_coercion_timeline())
        assert isinstance(out, dict)

    def test_required_keys(self):
        out = etd.get_economic_coercion_regression(_rising_coercion_timeline())
        for key in (
            "timeline_id", "score", "score_band",
            "structural_consistency_score", "timeline_sensitivity_score",
            "coercion_mechanism_score", "shock_mechanism_score",
            "buffer_mechanism_score",
            "assertions_passed", "assertions_failed", "scenario_results",
        ):
            assert key in out

    def test_score_band_correct(self):
        out = etd.get_economic_coercion_regression(_rising_coercion_timeline())
        assert out["score_band"] == etd._score_band(out["score"])

    def test_score_matches_validator(self):
        tl = _rising_coercion_timeline()
        out = etd.get_economic_coercion_regression(tl)
        assert out["score"] == run_economic_coercion_regression(tl).score

    def test_assertions_serialised_as_lists(self):
        out = etd.get_economic_coercion_regression(_rising_coercion_timeline())
        assert isinstance(out["assertions_passed"], list)
        assert isinstance(out["assertions_failed"], list)

    def test_n0_score_zero_band_fails_core(self):
        out = etd.get_economic_coercion_regression(
            TimelineEconomic(timeline_id="e", points=()))
        assert out["score"] == 0
        assert out["score_band"] == "Fails core logic"

    def test_propagates_value_error_on_bad_input(self):
        with pytest.raises(ValueError):
            etd.get_economic_coercion_regression("not a timeline")  # type: ignore[arg-type]


# ===========================================================================
# K. Endpoint
# ===========================================================================
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _make_user_session(app_module, username="alice"):
    import bcrypt
    import sessions_store
    import users_store

    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return sid


def _auth(sid):
    return {"X-Session-ID": sid}


class TestEndpoint:
    def test_valid_payload_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=_payload_from_timeline(_rising_coercion_timeline()),
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=_payload_from_timeline(_rising_coercion_timeline()),
            headers=_auth(sid),
        )
        body = resp.json()
        for k in ("timeline_id", "score", "score_band",
                  "coercion_mechanism_score", "shock_mechanism_score",
                  "buffer_mechanism_score", "scenario_results"):
            assert k in body

    def test_unauth_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=_payload_from_timeline(_rising_coercion_timeline()),
        )
        assert resp.status_code == 401

    def test_missing_timeline_id_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        del payload["timeline_id"]
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_list_points_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json={"timeline_id": "x", "points": "oops"},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_required_field_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        del payload["points"][0]["compliance_signal"]
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_numeric_field_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        payload["points"][0]["compliance_signal"] = "high"
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_bool_for_numeric_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        payload["points"][0]["compliance_signal"] = True
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_string_t_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        payload["points"][0]["t"] = 42
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_string_trigger_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        payload["points"][0]["trigger_event"] = 42
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_omitted_trigger_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        for p in payload["points"]:
            p.pop("trigger_event", None)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_empty_points_list_returns_200(self, client, app_module):
        """Unit 3 convention: empty timeline yields vacuous score-0 result."""
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json={"timeline_id": "empty", "points": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_empty_points_response_zero_band(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json={"timeline_id": "empty", "points": []},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["score"] == 0
        assert body["score_band"] == "Fails core logic"
        assert body["assertions_failed"] == []
        assert all(body["scenario_results"].values())

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        tl = _rising_coercion_timeline()
        direct = etd.get_economic_coercion_regression(tl)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=_payload_from_timeline(tl),
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_coercion_timeline())
        r1 = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid))
        r2 = client.post(
            "/elins/regression/economic_coercion",
            json=payload, headers=_auth(sid))
        assert r1.json() == r2.json()


# ===========================================================================
# L. Isolation — does not import basin inference modules
# ===========================================================================
class TestIsolation:
    def test_no_dashboard_import(self):
        src = inspect.getsource(ec)
        for pattern in ("import elins_dashboard", "from elins_dashboard"):
            assert pattern not in src

    def test_no_inference_imports(self):
        src = inspect.getsource(ec)
        for pattern in (
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


# ===========================================================================
# M. Independence from Unit 1 module
# ===========================================================================
class TestUnit1Independence:
    def test_does_not_import_unit_1_module(self):
        """Unit 4's regression module must be independent of Unit 1
        so changes in one cannot regress the other."""
        src = inspect.getsource(ec)
        for pattern in (
            "import elins_regression_single_party",
            "from elins_regression_single_party",
        ):
            assert pattern not in src

    def test_unit_1_validator_still_works(self):
        """Smoke: the Unit 1 validator imports cleanly alongside Unit 4."""
        from elins_regression_single_party import (
            Timeline, run_single_party_fear_regression,
        )
        r = run_single_party_fear_regression(
            Timeline(timeline_id="x", points=()))
        assert r.score == 0


# ===========================================================================
# N. End-to-end smoke
# ===========================================================================
class TestEndToEnd:
    def test_full_chain_rising_coercion(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=_payload_from_timeline(_rising_coercion_timeline()),
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["timeline_id"] == "rising_coercion"
        assert body["score"] >= 7
        assert set(body["scenario_results"].keys()) == {
            "test_1_rising_coercion",
            "test_2_economic_shock_event",
            "test_3_buffer_intervention",
            "test_4_coercion_substitution",
            "test_5_shock_without_coercion",
        }

    def test_existing_single_party_endpoint_still_works(self, client, app_module):
        """Adding the new endpoint did not break Unit 2's endpoint."""
        sid = _make_user_session(app_module)
        # A neutral single-party-fear payload that should pass cleanly.
        sp_payload = {
            "timeline_id": "neutral",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=sp_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200
