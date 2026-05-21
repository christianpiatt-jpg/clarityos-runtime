"""
Tests for ELINS Unit 1 — Single-Party Fear Regression Validator.

Layered coverage:
    A. Schemas — frozen + instantiable
    B. Helper math — mean/weighted_mean/trend_delta/etc.
    C. Derived variables — 4 functions, all formulas
    D. Scenario tests — 5 tests, positive + negative + vacuous
    E. Assertions — 6 assertions, pass + fail + vacuous
    F. Scoring rubric — each dimension + total boundaries (0,5,7,9,10)
    G. Determinism + purity (no mutation, no side effects)
    H. Source-code purity
    I. Module surface
    J. End-to-end timelines
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import elins_regression_single_party as reg
from elins_regression_single_party import (
    SinglePartyFearRegressionResult,
    Timeline,
    TimePoint,
    run_single_party_fear_regression,
)


# ===========================================================================
# Fixture builders
# ===========================================================================
def _tp(
    *,
    t: str = "t0",
    regime_competition: float = 0.5,
    autocratization: float = 0.5,
    repression_index: float = 0.5,
    digital_repression: float = 0.5,
    perceived_threat: float = 0.5,
    fear_signal: float = 0.5,
    dissent_capacity: float = 0.5,
    normative_constraint: float = 0.5,
    support_buffer: float = 0.5,
    trigger_event=None,
) -> TimePoint:
    return TimePoint(
        t=t,
        regime_competition=regime_competition,
        autocratization=autocratization,
        repression_index=repression_index,
        digital_repression=digital_repression,
        perceived_threat=perceived_threat,
        fear_signal=fear_signal,
        dissent_capacity=dissent_capacity,
        normative_constraint=normative_constraint,
        support_buffer=support_buffer,
        trigger_event=trigger_event,
    )


def _flat_timeline(n: int = 4, *, tid: str = "flat") -> Timeline:
    """Constant 0.5 across all variables — every scenario test should
    vacuously pass."""
    return Timeline(
        timeline_id=tid,
        points=tuple(_tp(t=f"t{i}") for i in range(n)),
    )


def _rising_concentration_timeline(*, tid: str = "rising") -> Timeline:
    """Rising single_party + autocratization + repression, declining
    constraint and competition."""
    return Timeline(
        timeline_id=tid,
        points=(
            _tp(t="t0", regime_competition=0.8, autocratization=0.2,
                repression_index=0.2, digital_repression=0.1,
                perceived_threat=0.2, fear_signal=0.2,
                dissent_capacity=0.8, normative_constraint=0.8,
                support_buffer=0.7),
            _tp(t="t1", regime_competition=0.6, autocratization=0.4,
                repression_index=0.4, digital_repression=0.3,
                perceived_threat=0.4, fear_signal=0.4,
                dissent_capacity=0.6, normative_constraint=0.6,
                support_buffer=0.6),
            _tp(t="t2", regime_competition=0.4, autocratization=0.6,
                repression_index=0.6, digital_repression=0.5,
                perceived_threat=0.6, fear_signal=0.6,
                dissent_capacity=0.4, normative_constraint=0.4,
                support_buffer=0.5, trigger_event="protests"),
            _tp(t="t3", regime_competition=0.2, autocratization=0.8,
                repression_index=0.9, digital_repression=0.7,
                perceived_threat=0.8, fear_signal=0.8,
                dissent_capacity=0.2, normative_constraint=0.2,
                support_buffer=0.4),
        ),
    )


def _crackdown_timeline(*, tid: str = "crackdown") -> Timeline:
    """Trigger event followed by repression spike + fear rise + dissent
    fall."""
    return Timeline(
        timeline_id=tid,
        points=(
            _tp(t="t0", regime_competition=0.5, autocratization=0.5,
                repression_index=0.3, digital_repression=0.3,
                perceived_threat=0.3, fear_signal=0.3,
                dissent_capacity=0.7, normative_constraint=0.5,
                support_buffer=0.5, trigger_event="emergency"),
            _tp(t="t1", regime_competition=0.5, autocratization=0.5,
                repression_index=0.7,                              # spike
                digital_repression=0.3,
                perceived_threat=0.4,
                fear_signal=0.5,                                   # +0.2
                dissent_capacity=0.5,                              # -0.2
                normative_constraint=0.5, support_buffer=0.5),
            _tp(t="t2", regime_competition=0.5, autocratization=0.5,
                repression_index=0.7, digital_repression=0.3,
                perceived_threat=0.5, fear_signal=0.6,
                dissent_capacity=0.4, normative_constraint=0.5,
                support_buffer=0.5),
        ),
    )


# ===========================================================================
# A. Schemas
# ===========================================================================
class TestSchemas:
    def test_timepoint_instantiable(self):
        p = _tp()
        assert p.regime_competition == 0.5

    def test_timepoint_frozen(self):
        p = _tp()
        with pytest.raises(FrozenInstanceError):
            p.regime_competition = 0.9  # type: ignore[misc]

    def test_timepoint_default_trigger_event_none(self):
        assert _tp().trigger_event is None

    def test_timeline_instantiable(self):
        tl = _flat_timeline(n=2)
        assert tl.timeline_id == "flat"
        assert len(tl.points) == 2

    def test_timeline_frozen(self):
        tl = _flat_timeline(n=2)
        with pytest.raises(FrozenInstanceError):
            tl.timeline_id = "x"  # type: ignore[misc]

    def test_result_instantiable(self):
        r = SinglePartyFearRegressionResult(
            timeline_id="x", score=10,
            structural_consistency_score=2,
            timeline_sensitivity_score=2,
            fear_mechanism_score=2,
            threat_mechanism_score=2,
            repression_coverage_score=2,
            assertions_passed=(), assertions_failed=(),
            scenario_results={}, derived_series={},
        )
        assert r.score == 10

    def test_result_frozen(self):
        r = SinglePartyFearRegressionResult(
            timeline_id="x", score=10,
            structural_consistency_score=2,
            timeline_sensitivity_score=2,
            fear_mechanism_score=2,
            threat_mechanism_score=2,
            repression_coverage_score=2,
            assertions_passed=(), assertions_failed=(),
            scenario_results={}, derived_series={},
        )
        with pytest.raises(FrozenInstanceError):
            r.score = 0  # type: ignore[misc]


# ===========================================================================
# B. Helper math
# ===========================================================================
class TestHelperMath:
    def test_mean_basic(self):
        assert reg._mean((1.0, 2.0, 3.0)) == 2.0

    def test_mean_empty(self):
        assert reg._mean(()) == 0.0

    def test_weighted_mean_equal_weights(self):
        result = reg._weighted_mean((1.0, 2.0, 3.0), (1.0, 1.0, 1.0))
        assert result == 2.0

    def test_weighted_mean_zero_weights(self):
        assert reg._weighted_mean((1.0, 2.0), (0.0, 0.0)) == 0.0

    def test_weighted_mean_empty(self):
        assert reg._weighted_mean((), ()) == 0.0

    def test_trend_delta_increasing(self):
        assert reg._trend_delta([0.1, 0.5, 0.9]) == pytest.approx(0.8)

    def test_trend_delta_decreasing(self):
        assert reg._trend_delta([0.9, 0.5, 0.1]) == pytest.approx(-0.8)

    def test_trend_delta_empty(self):
        assert reg._trend_delta([]) == 0.0

    def test_trend_delta_single_point(self):
        assert reg._trend_delta([0.5]) == 0.0

    def test_max_step_drop_no_drops(self):
        assert reg._max_step_drop([0.1, 0.2, 0.3]) == 0.0

    def test_max_step_drop_finds_largest(self):
        assert reg._max_step_drop([0.5, 0.2, 0.4, 0.1]) == pytest.approx(0.3)

    def test_sum_negative_deltas(self):
        assert reg._sum_negative_deltas([0.5, 0.3, 0.4, 0.2]) == pytest.approx(0.4)

    def test_pearson_sign_positive(self):
        assert reg._pearson_sign([1, 2, 3], [10, 20, 30]) == 1

    def test_pearson_sign_negative(self):
        assert reg._pearson_sign([1, 2, 3], [30, 20, 10]) == -1

    def test_pearson_sign_zero_variance(self):
        assert reg._pearson_sign([1, 1, 1], [1, 2, 3]) == 0

    def test_pearson_sign_too_short(self):
        assert reg._pearson_sign([1.0], [2.0]) == 0


# ===========================================================================
# C. Derived variables
# ===========================================================================
class TestDerivedVariables:
    def test_single_party_score_inverts_competition(self):
        p = _tp(regime_competition=0.7)
        assert reg._single_party_score(p) == pytest.approx(0.3)

    def test_single_party_score_at_zero_competition(self):
        p = _tp(regime_competition=0.0)
        assert reg._single_party_score(p) == 1.0

    def test_single_party_score_at_full_competition(self):
        p = _tp(regime_competition=1.0)
        assert reg._single_party_score(p) == 0.0

    def test_fear_pressure_average(self):
        p = _tp(perceived_threat=0.3, fear_signal=0.6, repression_index=0.9)
        assert reg._fear_pressure(p) == pytest.approx(0.6)

    def test_fear_pressure_all_zero(self):
        p = _tp(perceived_threat=0.0, fear_signal=0.0, repression_index=0.0)
        assert reg._fear_pressure(p) == 0.0

    def test_authoritarian_risk_equal_weights(self):
        # All inputs at 0.5 except normative_constraint also 0.5 →
        # (0.5, 0.5, 0.5, 0.5, 0.5, 0.5) → 0.5
        p = _tp()
        assert reg._authoritarian_risk(p) == pytest.approx(0.5)

    def test_authoritarian_risk_max(self):
        p = _tp(
            regime_competition=0.0, autocratization=1.0,
            repression_index=1.0, digital_repression=1.0,
            perceived_threat=1.0, normative_constraint=0.0,
        )
        assert reg._authoritarian_risk(p) == pytest.approx(1.0)

    def test_authoritarian_risk_min(self):
        p = _tp(
            regime_competition=1.0, autocratization=0.0,
            repression_index=0.0, digital_repression=0.0,
            perceived_threat=0.0, normative_constraint=1.0,
        )
        assert reg._authoritarian_risk(p) == 0.0

    def test_dissent_suppression_equal_weights(self):
        p = _tp()
        assert reg._dissent_suppression(p) == pytest.approx(0.5)

    def test_dissent_suppression_max(self):
        p = _tp(
            repression_index=1.0, fear_signal=1.0, perceived_threat=1.0,
            regime_competition=0.0, dissent_capacity=0.0,
        )
        assert reg._dissent_suppression(p) == pytest.approx(1.0)

    def test_build_derived_series_keys(self):
        derived = reg._build_derived_series(_flat_timeline(n=3))
        assert set(derived.keys()) == {
            "single_party_score", "fear_pressure",
            "authoritarian_risk", "dissent_suppression",
        }

    def test_build_derived_series_lengths_match_points(self):
        tl = _flat_timeline(n=5)
        derived = reg._build_derived_series(tl)
        for series in derived.values():
            assert len(series) == 5


# ===========================================================================
# D. Scenario tests
# ===========================================================================
class TestScenario1RisingConcentration:
    def test_pattern_present_passes(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_1_rising_concentration(tl, derived) is True

    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_1_rising_concentration(tl, derived) is True

    def test_pattern_present_but_repression_drops_sharply_fails(self):
        # Same as rising, but force repression_index to drop sharply at end.
        tl = Timeline(
            timeline_id="bad",
            points=(
                _tp(t="t0", regime_competition=0.8, autocratization=0.2,
                    normative_constraint=0.8, repression_index=0.9),
                _tp(t="t1", regime_competition=0.6, autocratization=0.4,
                    normative_constraint=0.6, repression_index=0.8),
                _tp(t="t2", regime_competition=0.4, autocratization=0.6,
                    normative_constraint=0.4, repression_index=0.7),
                _tp(t="t3", regime_competition=0.2, autocratization=0.8,
                    normative_constraint=0.2, repression_index=0.3),  # sharp drop
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_1_rising_concentration(tl, derived) is False


class TestScenario2CrackdownEvent:
    def test_pattern_present_passes(self):
        tl = _crackdown_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_2_crackdown_event(tl, derived) is True

    def test_pattern_absent_no_trigger_vacuously_passes(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_2_crackdown_event(tl, derived) is True

    def test_trigger_with_no_repression_spike_vacuously_passes(self):
        tl = Timeline(
            timeline_id="trigger_no_spike",
            points=(
                _tp(t="t0", trigger_event="protests", repression_index=0.3),
                _tp(t="t1", repression_index=0.35),  # no sharp jump
                _tp(t="t2", repression_index=0.4),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_2_crackdown_event(tl, derived) is True

    def test_repression_spike_without_fear_rise_fails(self):
        tl = Timeline(
            timeline_id="bad_crackdown",
            points=(
                _tp(t="t0", trigger_event="protests",
                    repression_index=0.3, fear_signal=0.3, dissent_capacity=0.7),
                _tp(t="t1", repression_index=0.7,        # spike
                    fear_signal=0.32, dissent_capacity=0.7),  # fear flat
                _tp(t="t2", repression_index=0.7,
                    fear_signal=0.32, dissent_capacity=0.7),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_2_crackdown_event(tl, derived) is False


class TestScenario3ThreatSpike:
    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_3_threat_spike_without_full_repression(tl, derived) is True

    def test_pattern_present_with_supportive_proxy_passes(self):
        tl = Timeline(
            timeline_id="threat_spike",
            points=(
                _tp(t="t0", perceived_threat=0.2, repression_index=0.4,
                    support_buffer=0.5),
                _tp(t="t1", perceived_threat=0.6, repression_index=0.45,
                    support_buffer=0.6),  # support_buffer rises (proxy ok)
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_3_threat_spike_without_full_repression(tl, derived) is True

    def test_pattern_present_with_falling_support_proxy_fails(self):
        tl = Timeline(
            timeline_id="threat_no_support",
            points=(
                _tp(t="t0", perceived_threat=0.2, repression_index=0.4,
                    support_buffer=0.7),
                _tp(t="t1", perceived_threat=0.6, repression_index=0.45,
                    support_buffer=0.4),  # falls 0.3 → fails
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_3_threat_spike_without_full_repression(tl, derived) is False


class TestScenario4ConstraintRestoration:
    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_4_constraint_restoration(tl, derived) is True

    def test_pattern_present_with_recovery_passes(self):
        tl = Timeline(
            timeline_id="restore",
            points=(
                _tp(t="t0", normative_constraint=0.3, support_buffer=0.3,
                    fear_signal=0.7, perceived_threat=0.7,
                    repression_index=0.7, dissent_capacity=0.3),
                _tp(t="t1", normative_constraint=0.6, support_buffer=0.6,
                    fear_signal=0.4, perceived_threat=0.4,
                    repression_index=0.4, dissent_capacity=0.5),
                _tp(t="t2", normative_constraint=0.8, support_buffer=0.8,
                    fear_signal=0.2, perceived_threat=0.2,
                    repression_index=0.2, dissent_capacity=0.7),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_4_constraint_restoration(tl, derived) is True

    def test_pattern_present_but_no_recovery_fails(self):
        tl = Timeline(
            timeline_id="restore_fail",
            points=(
                _tp(t="t0", normative_constraint=0.3, support_buffer=0.3,
                    fear_signal=0.4, perceived_threat=0.4,
                    repression_index=0.4, dissent_capacity=0.5,
                    autocratization=0.3, regime_competition=0.7,
                    digital_repression=0.3),
                _tp(t="t1", normative_constraint=0.7, support_buffer=0.7,
                    fear_signal=0.7, perceived_threat=0.7,         # rising
                    repression_index=0.7, dissent_capacity=0.3,
                    autocratization=0.7, regime_competition=0.3,
                    digital_repression=0.7),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_4_constraint_restoration(tl, derived) is False


class TestScenario5DigitalSubstitution:
    def test_pattern_absent_vacuously_passes(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._test_5_digital_substitution(tl, derived) is True

    def test_pattern_present_with_risk_rise_passes(self):
        tl = Timeline(
            timeline_id="digital_sub",
            points=(
                _tp(t="t0", digital_repression=0.2, repression_index=0.3,
                    autocratization=0.3, perceived_threat=0.3,
                    fear_signal=0.3, normative_constraint=0.7,
                    regime_competition=0.7),
                _tp(t="t1", digital_repression=0.7, repression_index=0.35,
                    autocratization=0.6, perceived_threat=0.5,
                    fear_signal=0.5, normative_constraint=0.4,
                    regime_competition=0.4),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._test_5_digital_substitution(tl, derived) is True


# ===========================================================================
# E. Assertions
# ===========================================================================
class TestAssertion1Monotonicity:
    def test_pass_on_rising_concentration(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_1_monotonicity(tl, derived) is True

    def test_vacuous_pass_when_pattern_absent(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_1_monotonicity(tl, derived) is True

    def test_fails_when_risk_declines_under_pattern(self):
        # Force a contradiction: pattern present but authoritarian_risk
        # declines. Construct a timeline where the formula's ingredients
        # somehow yield a falling risk. Use moderating fields to engineer.
        tl = Timeline(
            timeline_id="contradiction",
            points=(
                _tp(t="t0", regime_competition=0.2, autocratization=0.2,
                    normative_constraint=0.7,
                    repression_index=0.9, digital_repression=0.9,
                    perceived_threat=0.9),
                _tp(t="t1", regime_competition=0.0, autocratization=0.4,
                    normative_constraint=0.5,
                    repression_index=0.0, digital_repression=0.0,
                    perceived_threat=0.0),
            ),
        )
        derived = reg._build_derived_series(tl)
        # The pattern triggers (sp rises, auto rises, norm falls); risk falls.
        assert reg._assertion_1_monotonicity(tl, derived) is False


class TestAssertion2FearRepression:
    def test_pass_on_crackdown_with_fear_rise(self):
        tl = _crackdown_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_2_fear_repression(tl, derived) is True

    def test_vacuous_pass_with_no_trigger(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_2_fear_repression(tl, derived) is True

    def test_fails_when_repression_spikes_without_fear_or_offset(self):
        tl = Timeline(
            timeline_id="bad",
            points=(
                _tp(t="t0", trigger_event="purge",
                    repression_index=0.2, fear_signal=0.2,
                    support_buffer=0.5, normative_constraint=0.5),
                _tp(t="t1", repression_index=0.7,        # spike
                    fear_signal=0.2,                      # no rise
                    support_buffer=0.5, normative_constraint=0.5),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_2_fear_repression(tl, derived) is False

    def test_fear_offset_by_normative_constraint_passes(self):
        tl = Timeline(
            timeline_id="offset",
            points=(
                _tp(t="t0", trigger_event="emergency",
                    repression_index=0.2, fear_signal=0.2,
                    support_buffer=0.5, normative_constraint=0.4),
                _tp(t="t1", repression_index=0.7,        # spike
                    fear_signal=0.2,                      # no rise
                    support_buffer=0.5, normative_constraint=0.6),  # +0.2 offset
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_2_fear_repression(tl, derived) is True


class TestAssertion3ThreatAuthoritarian:
    def test_vacuous_pass_when_no_threat_rise(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_3_threat_authoritarian(tl, derived) is True

    def test_threat_rises_support_holds_passes(self):
        tl = Timeline(
            timeline_id="threat_holds",
            points=(
                _tp(t="t0", perceived_threat=0.2, support_buffer=0.5),
                _tp(t="t1", perceived_threat=0.6, support_buffer=0.5),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_3_threat_authoritarian(tl, derived) is True

    def test_threat_rises_support_falls_no_offset_fails(self):
        tl = Timeline(
            timeline_id="threat_drops",
            points=(
                _tp(t="t0", perceived_threat=0.2, support_buffer=0.7,
                    normative_constraint=0.5),
                _tp(t="t1", perceived_threat=0.6, support_buffer=0.4,
                    normative_constraint=0.5),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_3_threat_authoritarian(tl, derived) is False

    def test_threat_rises_support_falls_with_normative_offset_passes(self):
        tl = Timeline(
            timeline_id="threat_offset",
            points=(
                _tp(t="t0", perceived_threat=0.2, support_buffer=0.7,
                    normative_constraint=0.3),
                _tp(t="t1", perceived_threat=0.6, support_buffer=0.4,
                    normative_constraint=0.5),  # rises +0.2
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_3_threat_authoritarian(tl, derived) is True


class TestAssertion4DissentSuppression:
    def test_vacuous_pass_when_pattern_absent(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_4_dissent_suppression(tl, derived) is True

    def test_fear_and_repression_rise_dissent_falls_passes(self):
        tl = Timeline(
            timeline_id="suppression",
            points=(
                _tp(t="t0", fear_signal=0.2, repression_index=0.2,
                    dissent_capacity=0.8),
                _tp(t="t1", fear_signal=0.6, repression_index=0.6,
                    dissent_capacity=0.4),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_4_dissent_suppression(tl, derived) is True

    def test_fear_and_repression_rise_dissent_rises_fails(self):
        tl = Timeline(
            timeline_id="bad_dissent",
            points=(
                _tp(t="t0", fear_signal=0.2, repression_index=0.2,
                    dissent_capacity=0.4, normative_constraint=0.5,
                    support_buffer=0.5),
                _tp(t="t1", fear_signal=0.6, repression_index=0.6,
                    dissent_capacity=0.7,                          # rises
                    normative_constraint=0.5, support_buffer=0.5),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_4_dissent_suppression(tl, derived) is False

    def test_dissent_rise_with_strong_constraint_offset_passes(self):
        tl = Timeline(
            timeline_id="counter",
            points=(
                _tp(t="t0", fear_signal=0.2, repression_index=0.2,
                    dissent_capacity=0.4, normative_constraint=0.2,
                    support_buffer=0.5),
                _tp(t="t1", fear_signal=0.6, repression_index=0.6,
                    dissent_capacity=0.7,
                    normative_constraint=0.6,  # +0.4 strong offset
                    support_buffer=0.5),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_4_dissent_suppression(tl, derived) is True


class TestAssertion5Buffer:
    def test_vacuous_pass_when_pattern_absent(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_5_buffer(tl, derived) is True

    def test_buffer_and_constraint_rise_fear_pressure_dampens_passes(self):
        tl = Timeline(
            timeline_id="dampen",
            points=(
                _tp(t="t0", support_buffer=0.3, normative_constraint=0.3,
                    perceived_threat=0.7, fear_signal=0.7,
                    repression_index=0.7),
                _tp(t="t1", support_buffer=0.7, normative_constraint=0.7,
                    perceived_threat=0.3, fear_signal=0.3,
                    repression_index=0.3),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_5_buffer(tl, derived) is True

    def test_buffer_and_constraint_rise_but_fear_pressure_explodes_fails(self):
        tl = Timeline(
            timeline_id="explode",
            points=(
                _tp(t="t0", support_buffer=0.3, normative_constraint=0.3,
                    perceived_threat=0.2, fear_signal=0.2,
                    repression_index=0.2),
                _tp(t="t1", support_buffer=0.7, normative_constraint=0.7,
                    perceived_threat=0.9, fear_signal=0.9,
                    repression_index=0.9),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_5_buffer(tl, derived) is False


class TestAssertion6Substitution:
    def test_vacuous_pass_when_no_digital_rise(self):
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._assertion_6_substitution(tl, derived) is True

    def test_digital_rises_risk_rises_passes(self):
        tl = Timeline(
            timeline_id="digi",
            points=(
                _tp(t="t0", digital_repression=0.2),
                _tp(t="t1", digital_repression=0.7, autocratization=0.7,
                    perceived_threat=0.6, fear_signal=0.6,
                    repression_index=0.5,
                    normative_constraint=0.3),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_6_substitution(tl, derived) is True

    def test_digital_rises_risk_falls_fails(self):
        # Engineer: digital_repression rises but every other input falls
        # so authoritarian_risk falls.
        tl = Timeline(
            timeline_id="bad_digi",
            points=(
                _tp(t="t0", digital_repression=0.2,
                    regime_competition=0.0, autocratization=1.0,
                    repression_index=1.0, perceived_threat=1.0,
                    normative_constraint=0.0),
                _tp(t="t1", digital_repression=0.7,
                    regime_competition=1.0, autocratization=0.0,
                    repression_index=0.0, perceived_threat=0.0,
                    normative_constraint=1.0),
            ),
        )
        derived = reg._build_derived_series(tl)
        assert reg._assertion_6_substitution(tl, derived) is False


# ===========================================================================
# F. Scoring rubric
# ===========================================================================
class TestScoringDimensions:
    def test_repression_coverage_locked_at_two(self):
        """Structurally locked: authoritarian_risk's formula always
        includes both physical and digital repression."""
        tl = _flat_timeline()
        derived = reg._build_derived_series(tl)
        assert reg._score_repression_coverage(tl, derived) == 2

    def test_structural_consistency_in_range(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        score = reg._score_structural_consistency(tl, derived)
        assert 0 <= score <= 2

    def test_timeline_sensitivity_in_range(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        score = reg._score_timeline_sensitivity(tl, derived)
        assert 0 <= score <= 2

    def test_fear_mechanism_in_range(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        score = reg._score_fear_mechanism(tl, derived)
        assert 0 <= score <= 2

    def test_threat_mechanism_in_range(self):
        tl = _rising_concentration_timeline()
        derived = reg._build_derived_series(tl)
        score = reg._score_threat_mechanism(tl, derived)
        assert 0 <= score <= 2


class TestTotalScoreBoundaries:
    def test_flat_timeline_high_score(self):
        """A flat timeline triggers no failure modes, so scores are
        high (most dimensions award the point on absent input)."""
        r = run_single_party_fear_regression(_flat_timeline())
        assert r.score >= 7

    def test_rising_concentration_strong(self):
        """A clean rising-concentration timeline should hit Strong band
        (>= 9)."""
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        assert r.score >= 9

    def test_total_in_unit_range(self):
        for tl in (_flat_timeline(), _rising_concentration_timeline(),
                   _crackdown_timeline()):
            r = run_single_party_fear_regression(tl)
            assert 0 <= r.score <= 10

    def test_score_is_sum_of_dimensions(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        expected = (r.structural_consistency_score
                    + r.timeline_sensitivity_score
                    + r.fear_mechanism_score
                    + r.threat_mechanism_score
                    + r.repression_coverage_score)
        assert r.score == expected

    def test_scoring_thresholds_locked(self):
        """The threshold constants are locked."""
        assert reg.SCORE_STRONG_FLOOR == 9
        assert reg.SCORE_ACCEPTABLE_FLOOR == 7
        assert reg.SCORE_WEAK_FLOOR == 5


# ===========================================================================
# G. Determinism + purity
# ===========================================================================
class TestDeterminism:
    def test_same_timeline_byte_equal(self):
        tl = _rising_concentration_timeline()
        r1 = run_single_party_fear_regression(tl)
        r2 = run_single_party_fear_regression(tl)
        assert r1 == r2

    def test_timeline_not_mutated(self):
        tl = _rising_concentration_timeline()
        before = tuple(
            (p.t, p.regime_competition, p.autocratization,
             p.repression_index, p.fear_signal)
            for p in tl.points
        )
        run_single_party_fear_regression(tl)
        after = tuple(
            (p.t, p.regime_competition, p.autocratization,
             p.repression_index, p.fear_signal)
            for p in tl.points
        )
        assert before == after

    def test_repeated_calls_byte_equal_dicts(self):
        tl = _crackdown_timeline()
        r1 = run_single_party_fear_regression(tl)
        r2 = run_single_party_fear_regression(tl)
        assert r1.scenario_results == r2.scenario_results
        assert r1.derived_series == r2.derived_series


# ===========================================================================
# H. Source-code purity
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(reg)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports(self):
        src = self._src()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
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
# I. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_api_callable(self):
        assert callable(run_single_party_fear_regression)

    def test_constants_locked(self):
        assert reg._TREND_DELTA_THRESHOLD == 0.10
        assert reg._SHARP_STEP_THRESHOLD == 0.30
        assert reg._EVENT_RESPONSE_WINDOW == 3
        assert reg._NEAR_MONOTONIC_TOLERANCE == 0.20
        assert reg._MODEST_DELTA_THRESHOLD == 0.15

    def test_authoritarian_risk_weights_locked(self):
        assert reg._AUTHORITARIAN_RISK_WEIGHTS == (1.0,) * 6

    def test_dissent_suppression_weights_locked(self):
        assert reg._DISSENT_SUPPRESSION_WEIGHTS == (1.0,) * 5


# ===========================================================================
# J. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_non_timeline_raises_value_error(self):
        with pytest.raises(ValueError):
            run_single_party_fear_regression("not a timeline")  # type: ignore[arg-type]

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError):
            run_single_party_fear_regression(None)  # type: ignore[arg-type]

    def test_dict_raises_value_error(self):
        with pytest.raises(ValueError):
            run_single_party_fear_regression(  # type: ignore[arg-type]
                {"timeline_id": "x", "points": ()})


# ===========================================================================
# K. End-to-end timelines
# ===========================================================================
class TestEndToEnd:
    def test_full_result_contract(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        assert isinstance(r, SinglePartyFearRegressionResult)
        assert r.timeline_id == "rising"
        assert isinstance(r.score, int)
        assert isinstance(r.assertions_passed, tuple)
        assert isinstance(r.assertions_failed, tuple)
        assert isinstance(r.scenario_results, dict)
        assert isinstance(r.derived_series, dict)

    def test_all_six_assertions_accounted_for(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        all_assertions = set(r.assertions_passed) | set(r.assertions_failed)
        assert all_assertions == {
            "assertion_1_monotonicity",
            "assertion_2_fear_repression",
            "assertion_3_threat_authoritarian",
            "assertion_4_dissent_suppression",
            "assertion_5_buffer",
            "assertion_6_substitution",
        }

    def test_all_five_scenarios_accounted_for(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        assert set(r.scenario_results.keys()) == {
            "test_1_rising_concentration",
            "test_2_crackdown_event",
            "test_3_threat_spike_without_full_repression",
            "test_4_constraint_restoration",
            "test_5_digital_substitution",
        }

    def test_derived_series_contains_all_four(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        assert set(r.derived_series.keys()) == {
            "single_party_score", "fear_pressure",
            "authoritarian_risk", "dissent_suppression",
        }

    def test_two_point_timeline_runs(self):
        """Minimum viable timeline (2 points) doesn't crash."""
        tl = Timeline(
            timeline_id="tiny",
            points=(_tp(t="t0"), _tp(t="t1")),
        )
        r = run_single_party_fear_regression(tl)
        assert isinstance(r, SinglePartyFearRegressionResult)

    def test_single_point_timeline_runs(self):
        """Edge: one-point timeline. Trend deltas are 0 → most checks
        vacuously pass."""
        tl = Timeline(
            timeline_id="one",
            points=(_tp(t="t0"),),
        )
        r = run_single_party_fear_regression(tl)
        assert isinstance(r, SinglePartyFearRegressionResult)
        # All 4 derived series have length 1.
        for series in r.derived_series.values():
            assert len(series) == 1


# ===========================================================================
# L. ELINS Unit 3 — empty timeline (N=0) handled gracefully
# ===========================================================================
class TestEmptyTimelineBehavior:
    """Unit 3: an empty Timeline must not crash. The validator returns
    a vacuous, all-zero result (`Fails core logic` band)."""

    def _empty(self) -> Timeline:
        return Timeline(timeline_id="empty", points=())

    def test_returns_result_instance(self):
        r = run_single_party_fear_regression(self._empty())
        assert isinstance(r, SinglePartyFearRegressionResult)

    def test_total_score_is_zero(self):
        r = run_single_party_fear_regression(self._empty())
        assert r.score == 0

    def test_all_dimension_scores_zero(self):
        r = run_single_party_fear_regression(self._empty())
        assert r.structural_consistency_score == 0
        assert r.timeline_sensitivity_score == 0
        assert r.fear_mechanism_score == 0
        assert r.threat_mechanism_score == 0
        assert r.repression_coverage_score == 0

    def test_assertions_failed_is_empty(self):
        """No antecedent present → all 6 assertions vacuously pass."""
        r = run_single_party_fear_regression(self._empty())
        assert r.assertions_failed == ()

    def test_all_six_assertions_in_passed(self):
        r = run_single_party_fear_regression(self._empty())
        assert set(r.assertions_passed) == {
            "assertion_1_monotonicity",
            "assertion_2_fear_repression",
            "assertion_3_threat_authoritarian",
            "assertion_4_dissent_suppression",
            "assertion_5_buffer",
            "assertion_6_substitution",
        }

    def test_all_scenarios_pass_vacuously(self):
        r = run_single_party_fear_regression(self._empty())
        assert all(r.scenario_results.values())

    def test_all_five_scenarios_present(self):
        r = run_single_party_fear_regression(self._empty())
        assert set(r.scenario_results.keys()) == {
            "test_1_rising_concentration",
            "test_2_crackdown_event",
            "test_3_threat_spike_without_full_repression",
            "test_4_constraint_restoration",
            "test_5_digital_substitution",
        }

    def test_all_derived_series_empty_lists(self):
        r = run_single_party_fear_regression(self._empty())
        for key, series in r.derived_series.items():
            assert series == [], f"{key} should be empty list, got {series}"

    def test_timeline_id_preserved(self):
        r = run_single_party_fear_regression(self._empty())
        assert r.timeline_id == "empty"

    def test_determinism_byte_equal(self):
        r1 = run_single_party_fear_regression(self._empty())
        r2 = run_single_party_fear_regression(self._empty())
        assert r1 == r2

    def test_empty_timeline_does_not_raise(self):
        """The N=0 crash on max([]) in _score_fear_mechanism is fixed."""
        try:
            run_single_party_fear_regression(self._empty())
        except Exception as e:
            pytest.fail(f"empty timeline raised {type(e).__name__}: {e}")


# ===========================================================================
# M. Defense-in-depth: each scoring helper safely returns 0 on N=0
# ===========================================================================
class TestScoringHelpersN0Safety:
    """Each scoring helper must independently handle the N=0 case
    without crashing (defense-in-depth in case helpers are called
    directly outside run_single_party_fear_regression)."""

    def _empty_args(self):
        tl = Timeline(timeline_id="empty", points=())
        # An empty timeline yields empty derived series.
        derived = {
            "single_party_score":  [],
            "fear_pressure":       [],
            "authoritarian_risk":  [],
            "dissent_suppression": [],
        }
        return tl, derived

    def test_structural_consistency_returns_zero(self):
        tl, derived = self._empty_args()
        assert reg._score_structural_consistency(tl, derived) == 0

    def test_timeline_sensitivity_returns_zero(self):
        tl, derived = self._empty_args()
        assert reg._score_timeline_sensitivity(tl, derived) == 0

    def test_fear_mechanism_returns_zero_no_crash(self):
        tl, derived = self._empty_args()
        # Previously crashed with ValueError: max([]) — Unit 3 fixed.
        assert reg._score_fear_mechanism(tl, derived) == 0

    def test_threat_mechanism_returns_zero(self):
        tl, derived = self._empty_args()
        assert reg._score_threat_mechanism(tl, derived) == 0

    def test_repression_coverage_returns_zero(self):
        """Previously locked at 2; Unit 3 returns 0 for N=0."""
        tl, derived = self._empty_args()
        assert reg._score_repression_coverage(tl, derived) == 0


# ===========================================================================
# N. Non-empty behavior unchanged after Unit 3
# ===========================================================================
class TestNonEmptyBehaviorUnchanged:
    """Unit 3 must not regress N>=1 behavior."""

    def test_rising_timeline_still_strong(self):
        r = run_single_party_fear_regression(_rising_concentration_timeline())
        assert r.score >= 9

    def test_crackdown_timeline_assertion_2_passes(self):
        r = run_single_party_fear_regression(_crackdown_timeline())
        assert "assertion_2_fear_repression" in r.assertions_passed

    def test_repression_coverage_still_two_for_n_ge_one(self):
        """Coverage stays locked at 2 for any non-empty timeline."""
        r = run_single_party_fear_regression(_flat_timeline())
        assert r.repression_coverage_score == 2
