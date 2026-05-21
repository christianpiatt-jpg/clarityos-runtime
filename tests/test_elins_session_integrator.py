"""
Tests for ELINS13 Unit 33 — ELINS session integrator.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Session context pass-through
    C. ELINS block content
    D. Fusion history resolution precedence
    E. Append + fuse pipeline
    F. Decision + tag propagation from Unit 32
    G. Vault update correctness
    H. Vault-safe serialization (JSON round-trip)
    I. Determinism
    J. Validation — session_context
    K. Validation — elins_inputs
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import elins_operator_fusion as opf_mod
import elins_regime_fusion as rf_mod
import elins_session_integrator as si_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _structural() -> dict:
    """Minimal Unit 27 output."""
    return {
        "timeline":            [],
        "regime_class":        "stable",
        "volatility_variance": 0.001,
        "breakpoints":         [],
        "structural_events":   [],
        "summary":             "stable.",
    }


def _comparison(regime_delta: str = "same",
                risk: str = "low",
                baseline_regime: str = "stable",
                candidate_regime: str = "stable") -> dict:
    """Minimal Unit 29 output."""
    return {
        "regime_delta":    regime_delta,
        "risk_assessment": risk,
        "baseline":        {"regime_class": baseline_regime},
        "candidate":       {"regime_class": candidate_regime},
        # Unit 29 also surfaces these — surfaced here for downstream consumers.
        "volatility_delta":  {"absolute": 0.0, "relative": 0.0},
        "breakpoint_delta":  {
            "baseline_count": 0, "candidate_count": 0, "delta": 0,
        },
        "event_summary": {
            "new_events": [], "resolved_events": [], "persistent_events": [],
        },
        "summary": "",
    }


def _session_context(session_id: str = "sess_001",
                      operator_id: str = "op_alice",
                      timestamp: str = "2026-05-12T10:00:00+00:00",
                      vault_state=None,
                      runtime_flags=None) -> dict:
    return {
        "session_id":    session_id,
        "operator_id":   operator_id,
        "timestamp":     timestamp,
        "vault_state":   vault_state,
        "runtime_flags": runtime_flags or {
            "allow_overrides": True, "strict_mode": False,
        },
    }


def _elins_inputs(regime_delta: str = "same",
                   risk: str = "low",
                   fusion_history=None,
                   batches=None) -> dict:
    return {
        "batches":           batches or [],
        "cross_batch":       None,
        "trend":             None,
        "structural":        _structural(),
        "regime_comparison": _comparison(regime_delta, risk),
        "fusion_history":    fusion_history,
    }


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = si_mod.run_elins_session(_session_context(), _elins_inputs())
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp",
            "elins", "decision", "tags", "vault_update",
        }

    def test_elins_block_keys_locked(self):
        out = si_mod.run_elins_session(_session_context(), _elins_inputs())
        assert set(out["elins"].keys()) == {
            "structural", "regime", "fusion", "long_arc",
        }

    def test_vault_update_keys_locked(self):
        out = si_mod.run_elins_session(_session_context(), _elins_inputs())
        assert set(out["vault_update"].keys()) == {
            "fusion_history", "last_fusion", "last_long_arc",
        }


# ===========================================================================
# B. Session context pass-through
# ===========================================================================
class TestSessionContextPassthrough:
    def test_session_id_echoed(self):
        ctx = _session_context(session_id="custom_sess_123")
        out = si_mod.run_elins_session(ctx, _elins_inputs())
        assert out["session_id"] == "custom_sess_123"

    def test_operator_id_echoed(self):
        ctx = _session_context(operator_id="op_charlie")
        out = si_mod.run_elins_session(ctx, _elins_inputs())
        assert out["operator_id"] == "op_charlie"

    def test_timestamp_echoed(self):
        ctx = _session_context(timestamp="2030-01-01T00:00:00Z")
        out = si_mod.run_elins_session(ctx, _elins_inputs())
        assert out["timestamp"] == "2030-01-01T00:00:00Z"


# ===========================================================================
# C. ELINS block content
# ===========================================================================
class TestElinsBlock:
    def test_structural_passthrough(self):
        ctx = _session_context()
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(ctx, inputs)
        assert out["elins"]["structural"] == inputs["structural"]

    def test_regime_equals_regime_comparison_input(self):
        ctx = _session_context()
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(ctx, inputs)
        assert out["elins"]["regime"] == inputs["regime_comparison"]

    def test_fusion_matches_unit_31(self):
        ctx = _session_context()
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(ctx, inputs)
        # Re-derive Unit 31 over the same appended history.
        history = (inputs.get("fusion_history") or []) + [
            inputs["regime_comparison"],
        ]
        expected = rf_mod.fuse_regime_history(history)
        assert out["elins"]["fusion"] == expected

    def test_long_arc_matches_unit_32(self):
        ctx = _session_context()
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(ctx, inputs)
        history = [inputs["regime_comparison"]]
        expected = opf_mod.evaluate_long_arc(history)
        assert out["elins"]["long_arc"] == expected


# ===========================================================================
# D. Fusion history resolution precedence
# ===========================================================================
class TestFusionHistoryResolution:
    def test_uses_elins_inputs_history_when_present(self):
        prior = [_comparison("degraded", "high")]
        inputs = _elins_inputs(fusion_history=prior)
        out = si_mod.run_elins_session(_session_context(), inputs)
        # vault_update.fusion_history = prior + new comparison.
        assert out["vault_update"]["fusion_history"] == \
               prior + [inputs["regime_comparison"]]

    def test_uses_vault_state_history_when_inputs_history_none(self):
        prior = [_comparison("degraded", "high")]
        ctx = _session_context(
            vault_state={"fusion_history": prior},
        )
        inputs = _elins_inputs(fusion_history=None)
        out = si_mod.run_elins_session(ctx, inputs)
        assert out["vault_update"]["fusion_history"] == \
               prior + [inputs["regime_comparison"]]

    def test_inputs_history_wins_over_vault_state(self):
        # Both provided — inputs takes precedence per spec.
        from_inputs = [_comparison("improved", "low")]
        from_vault  = [_comparison("degraded", "high")]
        ctx = _session_context(
            vault_state={"fusion_history": from_vault},
        )
        inputs = _elins_inputs(fusion_history=from_inputs)
        out = si_mod.run_elins_session(ctx, inputs)
        # History is from_inputs + new comparison; from_vault is ignored.
        assert out["vault_update"]["fusion_history"][:len(from_inputs)] == \
               from_inputs

    def test_empty_when_neither_present(self):
        inputs = _elins_inputs(fusion_history=None)
        out = si_mod.run_elins_session(_session_context(), inputs)
        # History is just the new comparison.
        assert out["vault_update"]["fusion_history"] == [
            inputs["regime_comparison"],
        ]

    def test_input_history_not_mutated(self):
        prior = [_comparison("degraded", "high")]
        prior_snapshot = list(prior)
        si_mod.run_elins_session(
            _session_context(),
            _elins_inputs(fusion_history=prior),
        )
        # Input list unchanged after the call.
        assert prior == prior_snapshot


# ===========================================================================
# E. Append + fuse pipeline
# ===========================================================================
class TestAppendAndFuse:
    def test_new_comparison_appended_to_history(self):
        prior = [_comparison("same", "low")]
        inputs = _elins_inputs(fusion_history=prior,
                                regime_delta="degraded", risk="high")
        out = si_mod.run_elins_session(_session_context(), inputs)
        history = out["vault_update"]["fusion_history"]
        assert history[-1] == inputs["regime_comparison"]
        assert len(history) == 2

    def test_fusion_uses_updated_history(self):
        prior = [_comparison("same", "low")]
        inputs = _elins_inputs(fusion_history=prior,
                                regime_delta="degraded", risk="high")
        out = si_mod.run_elins_session(_session_context(), inputs)
        expected = rf_mod.fuse_regime_history(
            prior + [inputs["regime_comparison"]],
        )
        assert out["elins"]["fusion"] == expected

    def test_long_arc_uses_updated_history(self):
        prior = [_comparison("degraded", "high") for _ in range(3)]
        inputs = _elins_inputs(fusion_history=prior,
                                regime_delta="degraded", risk="high")
        out = si_mod.run_elins_session(_session_context(), inputs)
        expected = opf_mod.evaluate_long_arc(
            prior + [inputs["regime_comparison"]],
        )
        assert out["elins"]["long_arc"] == expected


# ===========================================================================
# F. Decision + tag propagation from Unit 32
# ===========================================================================
class TestDecisionPropagation:
    def test_decision_matches_unit_32(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        expected = opf_mod.evaluate_long_arc([inputs["regime_comparison"]])
        assert out["decision"] == expected["decision"]

    def test_tags_match_unit_32(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        expected = opf_mod.evaluate_long_arc([inputs["regime_comparison"]])
        assert out["tags"] == expected["tags"]

    def test_persistent_degradation_history_blocks(self):
        prior = [_comparison("degraded", "high") for _ in range(3)]
        inputs = _elins_inputs(fusion_history=prior,
                                regime_delta="degraded", risk="high")
        out = si_mod.run_elins_session(_session_context(), inputs)
        # 4 degraded + high risk → persistent_degradation → block.
        assert out["decision"] == "block"

    def test_stable_history_allows(self):
        prior = [_comparison("improved", "low") for _ in range(2)]
        inputs = _elins_inputs(fusion_history=prior,
                                regime_delta="improved", risk="low")
        out = si_mod.run_elins_session(_session_context(), inputs)
        assert out["decision"] == "allow"


# ===========================================================================
# G. Vault update correctness
# ===========================================================================
class TestVaultUpdate:
    def test_fusion_history_in_vault_update(self):
        prior = [_comparison("same", "low")]
        inputs = _elins_inputs(fusion_history=prior)
        out = si_mod.run_elins_session(_session_context(), inputs)
        assert "fusion_history" in out["vault_update"]
        assert isinstance(out["vault_update"]["fusion_history"], list)

    def test_last_fusion_matches_unit_31(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        assert out["vault_update"]["last_fusion"] == out["elins"]["fusion"]

    def test_last_long_arc_matches_unit_32(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        assert out["vault_update"]["last_long_arc"] == \
               out["elins"]["long_arc"]

    def test_vault_update_history_includes_new_comparison(self):
        inputs = _elins_inputs(regime_delta="degraded", risk="medium")
        out = si_mod.run_elins_session(_session_context(), inputs)
        assert inputs["regime_comparison"] in \
               out["vault_update"]["fusion_history"]


# ===========================================================================
# H. Vault-safe serialization (JSON round-trip)
# ===========================================================================
class TestVaultSafeSerialization:
    def test_output_is_json_serializable(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        # If json.dumps succeeds without `default=`, no Python-only
        # types snuck through.
        encoded = json.dumps(out)
        decoded = json.loads(encoded)
        assert decoded["session_id"] == out["session_id"]

    def test_no_tuples_in_output(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        # tuple-bearing values would fail JSON encode without `default=`
        # — already covered by the round-trip above; this is a defensive
        # walk for clarity.
        def _walk(obj):
            assert not isinstance(obj, tuple)
            if isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    _walk(v)
        _walk(out)

    def test_tags_are_strings(self):
        inputs = _elins_inputs()
        out = si_mod.run_elins_session(_session_context(), inputs)
        for tag in out["tags"]:
            assert isinstance(tag, str)


# ===========================================================================
# I. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        ctx = _session_context()
        inputs = _elins_inputs()
        a = si_mod.run_elins_session(ctx, inputs)
        b = si_mod.run_elins_session(ctx, inputs)
        assert a == b

    def test_byte_equal_with_history(self):
        ctx = _session_context()
        inputs = _elins_inputs(
            fusion_history=[_comparison("degraded", "high") for _ in range(3)],
            regime_delta="degraded", risk="high",
        )
        a = si_mod.run_elins_session(ctx, inputs)
        b = si_mod.run_elins_session(ctx, inputs)
        assert a == b


# ===========================================================================
# J. Validation — session_context
# ===========================================================================
class TestSessionContextValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="session_context"):
            si_mod.run_elins_session("nope", _elins_inputs())

    def test_missing_session_id_raises(self):
        bad = _session_context()
        del bad["session_id"]
        with pytest.raises(ValueError, match="session_id"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_missing_operator_id_raises(self):
        bad = _session_context()
        del bad["operator_id"]
        with pytest.raises(ValueError, match="operator_id"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_missing_timestamp_raises(self):
        bad = _session_context()
        del bad["timestamp"]
        with pytest.raises(ValueError, match="timestamp"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_non_string_session_id_raises(self):
        bad = _session_context()
        bad["session_id"] = 123
        with pytest.raises(ValueError, match="session_id"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_empty_session_id_raises(self):
        bad = _session_context()
        bad["session_id"] = ""
        with pytest.raises(ValueError, match="session_id"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_non_dict_vault_state_raises(self):
        bad = _session_context(vault_state="nope")
        with pytest.raises(ValueError, match="vault_state"):
            si_mod.run_elins_session(bad, _elins_inputs())

    def test_none_vault_state_ok(self):
        ctx = _session_context(vault_state=None)
        out = si_mod.run_elins_session(ctx, _elins_inputs())
        assert "session_id" in out


# ===========================================================================
# K. Validation — elins_inputs
# ===========================================================================
class TestElinsInputsValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="elins_inputs"):
            si_mod.run_elins_session(_session_context(), "nope")

    def test_missing_structural_raises(self):
        bad = _elins_inputs()
        del bad["structural"]
        with pytest.raises(ValueError, match="structural"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_missing_regime_comparison_raises(self):
        bad = _elins_inputs()
        del bad["regime_comparison"]
        with pytest.raises(ValueError, match="regime_comparison"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_non_dict_structural_raises(self):
        bad = _elins_inputs()
        bad["structural"] = "nope"
        with pytest.raises(ValueError, match="structural"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_non_dict_regime_comparison_raises(self):
        bad = _elins_inputs()
        bad["regime_comparison"] = "nope"
        with pytest.raises(ValueError, match="regime_comparison"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_regime_comparison_missing_unit_29_keys_raises(self):
        bad = _elins_inputs()
        bad["regime_comparison"] = {"regime_delta": "same"}
        with pytest.raises(ValueError, match="Unit 29 key"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_non_list_fusion_history_raises(self):
        bad = _elins_inputs()
        bad["fusion_history"] = "nope"
        with pytest.raises(ValueError, match="fusion_history"):
            si_mod.run_elins_session(_session_context(), bad)

    def test_none_fusion_history_ok(self):
        inputs = _elins_inputs(fusion_history=None)
        out = si_mod.run_elins_session(_session_context(), inputs)
        # Empty starting history → updated has just the new comparison.
        assert len(out["vault_update"]["fusion_history"]) == 1


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(si_mod.run_elins_session)

    def test_required_session_keys_locked(self):
        assert si_mod._REQUIRED_SESSION_KEYS == (
            "session_id", "operator_id", "timestamp",
        )

    def test_required_elins_input_keys_locked(self):
        assert si_mod._REQUIRED_ELINS_INPUT_KEYS == (
            "structural", "regime_comparison",
        )

    def test_required_regime_keys_locked(self):
        assert si_mod._REQUIRED_REGIME_KEYS == (
            "regime_delta", "risk_assessment", "baseline", "candidate",
        )


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(si_mod)

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
        # Unit 33 is the bridge — it must not touch ELINS persistence
        # or vault storage directly. RuntimeKernel owns those.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result", "vault_store", "memory_vault",
        ):
            assert forbidden not in src

    def test_composes_units_31_and_32(self):
        src = self._code_only()
        assert "fuse_regime_history" in src
        assert "evaluate_long_arc" in src
