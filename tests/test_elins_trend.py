"""
Tests for ELINS9 Unit 25 — cross-batch temporal trend engine.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Timeline section content
    C. Slope correctness (OLS math)
    D. Direction thresholds
    E. Event detection (vocabulary + alpha sort)
    F. Summary string content
    G. Small-N (0 / 1 / 2 entries)
    H. Per-batch aggregate parity
    I. Input order preserved (caller-supplied chronological)
    J. Determinism (byte-equal repeats)
    K. Validation
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_trend as tr_mod


# ===========================================================================
# Fixtures — synthetic Unit 21 outputs (no DB)
# ===========================================================================
def _group_payload(decision: str,
                   health: float,
                   anomaly: float = 0.0,
                   regressions: int = 0) -> dict:
    return {
        "decision": decision,
        "reasons":  [],
        "metrics": {
            "health":           health,
            "anomaly_fraction": anomaly,
            "trend_shift":      "neutral",
            "cluster_shift":    "neutral",
            "regressions":      regressions,
            "promoted_pairs":   [],
        },
    }


def _batch_payload(groups: dict) -> dict:
    return {"groups": groups, "comparisons": {}}


def _single_group_batch(decision: str = "allow",
                         health: float = 0.8,
                         anomaly: float = 0.05,
                         regressions: int = 0) -> dict:
    return _batch_payload({
        "g0": _group_payload(decision, health, anomaly, regressions),
    })


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        timeline = [
            ("2026-05-01", _single_group_batch(health=0.8)),
            ("2026-05-08", _single_group_batch(health=0.82)),
            ("2026-05-15", _single_group_batch(health=0.84)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert set(out.keys()) == {
            "timeline", "trend_vectors", "events", "summary",
        }

    def test_timeline_is_list(self):
        timeline = [
            ("2026-01-01", _single_group_batch()),
            ("2026-01-08", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert isinstance(out["timeline"], list)

    def test_trend_vectors_keys_locked(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert set(out["trend_vectors"].keys()) == {
            "health", "anomaly", "regressions",
        }

    def test_each_trend_vector_keys_locked(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        for v in out["trend_vectors"].values():
            assert set(v.keys()) == {"slope", "direction"}

    def test_summary_is_string(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert isinstance(out["summary"], str)


# ===========================================================================
# B. Timeline section content
# ===========================================================================
class TestTimelineSection:
    def test_one_entry_per_input(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
            ("c", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert len(out["timeline"]) == 3

    def test_entry_keys_locked(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert set(out["timeline"][0].keys()) == {
            "timestamp", "mean_health",
            "mean_anomaly_fraction",
            "total_regressions", "group_count",
        }

    def test_timestamps_preserved(self):
        timeline = [
            ("2026-05-01", _single_group_batch()),
            ("2026-05-08", _single_group_batch()),
            ("2026-05-15", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert [e["timestamp"] for e in out["timeline"]] == [
            "2026-05-01", "2026-05-08", "2026-05-15",
        ]

    def test_health_values_match_batch_means(self):
        timeline = [
            ("a", _single_group_batch(health=0.6)),
            ("b", _single_group_batch(health=0.8)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][0]["mean_health"] == pytest.approx(0.6)
        assert out["timeline"][1]["mean_health"] == pytest.approx(0.8)

    def test_anomaly_values_match_batch_means(self):
        timeline = [
            ("a", _single_group_batch(anomaly=0.10)),
            ("b", _single_group_batch(anomaly=0.20)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][0]["mean_anomaly_fraction"] == \
               pytest.approx(0.10)
        assert out["timeline"][1]["mean_anomaly_fraction"] == \
               pytest.approx(0.20)

    def test_regressions_values_match_batch_totals(self):
        timeline = [
            ("a", _single_group_batch(regressions=1)),
            ("b", _single_group_batch(regressions=3)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][0]["total_regressions"] == 1
        assert out["timeline"][1]["total_regressions"] == 3

    def test_group_count_correct(self):
        batch_2 = _batch_payload({
            "g0": _group_payload("allow", 0.8),
            "g1": _group_payload("allow", 0.8),
        })
        timeline = [
            ("a", _single_group_batch()),
            ("b", batch_2),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][0]["group_count"] == 1
        assert out["timeline"][1]["group_count"] == 2


# ===========================================================================
# C. Slope correctness
# ===========================================================================
class TestSlopeMath:
    def test_n2_slope_equals_delta(self):
        # OLS slope of two points is exactly y1 - y0.
        timeline = [
            ("a", _single_group_batch(health=0.50)),
            ("b", _single_group_batch(health=0.80)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["slope"] == pytest.approx(0.30)

    def test_n3_constant_slope_zero(self):
        timeline = [
            ("a", _single_group_batch(health=0.80)),
            ("b", _single_group_batch(health=0.80)),
            ("c", _single_group_batch(health=0.80)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["slope"] == pytest.approx(0.0)

    def test_n3_increasing_positive_slope(self):
        timeline = [
            ("a", _single_group_batch(health=0.50)),
            ("b", _single_group_batch(health=0.60)),
            ("c", _single_group_batch(health=0.70)),
        ]
        out = tr_mod.analyze_trends(timeline)
        # Linear with step 0.10 → OLS slope is 0.10.
        assert out["trend_vectors"]["health"]["slope"] == pytest.approx(0.10)

    def test_n3_decreasing_negative_slope(self):
        timeline = [
            ("a", _single_group_batch(health=0.80)),
            ("b", _single_group_batch(health=0.60)),
            ("c", _single_group_batch(health=0.40)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["slope"] == pytest.approx(-0.20)

    def test_anomaly_slope_independent_of_health(self):
        timeline = [
            ("a", _single_group_batch(health=0.5, anomaly=0.10)),
            ("b", _single_group_batch(health=0.5, anomaly=0.20)),
            ("c", _single_group_batch(health=0.5, anomaly=0.30)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["slope"] == pytest.approx(0.0)
        assert out["trend_vectors"]["anomaly"]["slope"] == pytest.approx(0.10)

    def test_regressions_slope_integer_input(self):
        timeline = [
            ("a", _single_group_batch(regressions=0)),
            ("b", _single_group_batch(regressions=2)),
            ("c", _single_group_batch(regressions=4)),
        ]
        out = tr_mod.analyze_trends(timeline)
        # Slope is 2.0 per timestep.
        assert out["trend_vectors"]["regressions"]["slope"] == \
               pytest.approx(2.0)


# ===========================================================================
# D. Direction thresholds
# ===========================================================================
class TestDirectionThresholds:
    def test_up_when_slope_above_epsilon(self):
        timeline = [
            ("a", _single_group_batch(health=0.50)),
            ("b", _single_group_batch(health=0.60)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "up"

    def test_down_when_slope_below_neg_epsilon(self):
        timeline = [
            ("a", _single_group_batch(health=0.80)),
            ("b", _single_group_batch(health=0.60)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "down"

    def test_flat_when_slope_zero(self):
        timeline = [
            ("a", _single_group_batch(health=0.70)),
            ("b", _single_group_batch(health=0.70)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "flat"

    def test_flat_when_slope_within_epsilon(self):
        # Slope of 0.005 is below the 0.01 threshold.
        timeline = [
            ("a", _single_group_batch(health=0.700)),
            ("b", _single_group_batch(health=0.705)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "flat"

    def test_just_under_epsilon_is_flat(self):
        # Slope of 0.009 sits just below the 0.01 cutoff and must read
        # flat. (Using float-safe deltas — anything below the cutoff
        # by a clear margin avoids IEEE-754 rounding ambiguity at the
        # exact boundary.)
        timeline = [
            ("a", _single_group_batch(health=0.500)),
            ("b", _single_group_batch(health=0.509)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "flat"

    def test_just_over_epsilon_is_up(self):
        timeline = [
            ("a", _single_group_batch(health=0.500)),
            ("b", _single_group_batch(health=0.520)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"]["health"]["direction"] == "up"


# ===========================================================================
# E. Event detection (vocabulary + alpha sort)
# ===========================================================================
class TestEvents:
    def test_health_improving_event_fires(self):
        timeline = [
            ("a", _single_group_batch(health=0.5)),
            ("b", _single_group_batch(health=0.6)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "health_improving" in out["events"]

    def test_health_deteriorating_event_fires(self):
        timeline = [
            ("a", _single_group_batch(health=0.8)),
            ("b", _single_group_batch(health=0.5)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "health_deteriorating" in out["events"]

    def test_anomaly_rising_event_fires(self):
        timeline = [
            ("a", _single_group_batch(health=0.7, anomaly=0.10)),
            ("b", _single_group_batch(health=0.7, anomaly=0.30)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "anomaly_rising" in out["events"]

    def test_anomaly_falling_event_fires(self):
        timeline = [
            ("a", _single_group_batch(anomaly=0.30)),
            ("b", _single_group_batch(anomaly=0.10)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "anomaly_falling" in out["events"]

    def test_regressions_increasing_event_fires(self):
        timeline = [
            ("a", _single_group_batch(regressions=0)),
            ("b", _single_group_batch(regressions=4)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "regressions_increasing" in out["events"]

    def test_regressions_decreasing_event_fires(self):
        timeline = [
            ("a", _single_group_batch(regressions=5)),
            ("b", _single_group_batch(regressions=1)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "regressions_decreasing" in out["events"]

    def test_flat_universe_no_events(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["events"] == []

    def test_events_alpha_sorted(self):
        timeline = [
            ("a", _single_group_batch(health=0.8, anomaly=0.10, regressions=5)),
            ("b", _single_group_batch(health=0.5, anomaly=0.30, regressions=1)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["events"] == sorted(out["events"])

    def test_events_unique(self):
        timeline = [
            ("a", _single_group_batch(health=0.5)),
            ("b", _single_group_batch(health=0.7)),
            ("c", _single_group_batch(health=0.9)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert len(out["events"]) == len(set(out["events"]))


# ===========================================================================
# F. Summary string content
# ===========================================================================
class TestSummary:
    def test_summary_non_empty(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["summary"].strip() != ""

    def test_summary_mentions_health_when_trending(self):
        timeline = [
            ("a", _single_group_batch(health=0.5)),
            ("b", _single_group_batch(health=0.8)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "Health" in out["summary"]
        assert "upward" in out["summary"].lower()

    def test_summary_mentions_flat_when_stable(self):
        timeline = [
            ("a", _single_group_batch()),
            ("b", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "flat" in out["summary"].lower()

    def test_summary_mentions_anomalies(self):
        timeline = [
            ("a", _single_group_batch(anomaly=0.10)),
            ("b", _single_group_batch(anomaly=0.30)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "anomalies" in out["summary"].lower()

    def test_summary_mentions_regressions(self):
        timeline = [
            ("a", _single_group_batch(regressions=0)),
            ("b", _single_group_batch(regressions=4)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert "regressions" in out["summary"].lower()


# ===========================================================================
# G. Small-N (0 / 1 / 2)
# ===========================================================================
class TestSmallN:
    def test_empty_returns_insufficient_data(self):
        out = tr_mod.analyze_trends([])
        assert out["events"] == ["insufficient_data"]

    def test_empty_has_flat_directions(self):
        out = tr_mod.analyze_trends([])
        for v in out["trend_vectors"].values():
            assert v["direction"] == "flat"
            assert v["slope"] == 0.0

    def test_empty_timeline_section_empty(self):
        out = tr_mod.analyze_trends([])
        assert out["timeline"] == []

    def test_single_entry_returns_insufficient_data(self):
        timeline = [("a", _single_group_batch())]
        out = tr_mod.analyze_trends(timeline)
        assert out["events"] == ["insufficient_data"]

    def test_single_entry_timeline_section_populated(self):
        timeline = [("a", _single_group_batch())]
        out = tr_mod.analyze_trends(timeline)
        # Timeline aggregates are still emitted — caller may want them
        # even when no trend is computable.
        assert len(out["timeline"]) == 1

    def test_two_entries_compute_trend(self):
        timeline = [
            ("a", _single_group_batch(health=0.5)),
            ("b", _single_group_batch(health=0.7)),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["events"] != ["insufficient_data"]


# ===========================================================================
# H. Per-batch aggregate parity
# ===========================================================================
class TestAggregateParity:
    def test_multiple_groups_mean_health(self):
        batch = _batch_payload({
            "g0": _group_payload("allow", 0.6),
            "g1": _group_payload("allow", 0.8),
        })
        timeline = [
            ("a", _single_group_batch(health=0.7)),
            ("b", batch),
        ]
        out = tr_mod.analyze_trends(timeline)
        # Second batch mean = (0.6 + 0.8) / 2 = 0.7.
        assert out["timeline"][1]["mean_health"] == pytest.approx(0.7)

    def test_multiple_groups_total_regressions(self):
        batch = _batch_payload({
            "g0": _group_payload("allow", 0.8, regressions=1),
            "g1": _group_payload("allow", 0.8, regressions=3),
        })
        timeline = [
            ("a", _single_group_batch()),
            ("b", batch),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][1]["total_regressions"] == 4

    def test_empty_groups_zero_aggregates(self):
        batch = _batch_payload({})
        timeline = [
            ("a", _single_group_batch()),
            ("b", batch),
        ]
        out = tr_mod.analyze_trends(timeline)
        assert out["timeline"][1]["mean_health"] == 0.0
        assert out["timeline"][1]["group_count"] == 0


# ===========================================================================
# I. Input order preserved
# ===========================================================================
class TestOrderPreservation:
    def test_input_order_preserved_alpha_input(self):
        timeline = [
            ("z", _single_group_batch()),
            ("a", _single_group_batch()),
        ]
        out = tr_mod.analyze_trends(timeline)
        # No re-sorting; caller-supplied order is canonical.
        assert [e["timestamp"] for e in out["timeline"]] == ["z", "a"]

    def test_list_entry_form_accepted(self):
        # Tuples and lists both work for entries.
        timeline = [
            ["a", _single_group_batch()],
            ["b", _single_group_batch()],
        ]
        out = tr_mod.analyze_trends(timeline)
        assert len(out["timeline"]) == 2


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        timeline = [
            ("a", _single_group_batch(health=0.6)),
            ("b", _single_group_batch(health=0.7)),
            ("c", _single_group_batch(health=0.8)),
        ]
        a = tr_mod.analyze_trends(timeline)
        b = tr_mod.analyze_trends(timeline)
        assert a == b

    def test_byte_equal_empty(self):
        a = tr_mod.analyze_trends([])
        b = tr_mod.analyze_trends([])
        assert a == b

    def test_byte_equal_insufficient_data(self):
        a = tr_mod.analyze_trends([("a", _single_group_batch())])
        b = tr_mod.analyze_trends([("a", _single_group_batch())])
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            tr_mod.analyze_trends("nope")

    def test_dict_top_level_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            tr_mod.analyze_trends({})

    def test_entry_not_tuple_raises(self):
        with pytest.raises(ValueError, match="tuple"):
            tr_mod.analyze_trends(["nope"])

    def test_entry_wrong_length_raises(self):
        with pytest.raises(ValueError, match="length 2"):
            tr_mod.analyze_trends([("a",)])

    def test_non_string_timestamp_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            tr_mod.analyze_trends([(123, _single_group_batch())])

    def test_empty_timestamp_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            tr_mod.analyze_trends([("", _single_group_batch())])

    def test_non_dict_payload_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            tr_mod.analyze_trends([("a", "nope")])

    def test_missing_groups_key_raises(self):
        with pytest.raises(ValueError, match="'groups'"):
            tr_mod.analyze_trends([("a", {"comparisons": {}})])


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(tr_mod.analyze_trends)

    def test_direction_epsilon_locked(self):
        assert tr_mod._DIRECTION_EPSILON == 0.01

    def test_direction_vocabulary_locked(self):
        assert tr_mod._DIR_UP   == "up"
        assert tr_mod._DIR_DOWN == "down"
        assert tr_mod._DIR_FLAT == "flat"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(tr_mod)

    def _code_only(self) -> str:
        import re as _re
        src = self._src()
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_persistence_imports(self):
        # Unit 25 operates over already-computed Unit 21 outputs — it
        # must not touch the runs persistence layer.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result",
        ):
            assert forbidden not in src
