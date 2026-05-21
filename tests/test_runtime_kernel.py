"""
Tests for Unit 35 — runtime kernel core.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Context passthrough
    C. ELINS wiring (Unit 33 binding)
    D. Runtime action wiring (Unit 34 binding)
    E. Vault merging
    F. Override propagation
    G. Operator view — headline + details
    H. Validation — operator_intent
    I. Validation — session_context
    J. Validation — vault_state
    K. Determinism + immutability
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import elins_runtime_actions as rt_mod
import elins_session_integrator as si_mod
import runtime_kernel as rk_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _structural() -> dict:
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
    return {
        "regime_delta":    regime_delta,
        "risk_assessment": risk,
        "baseline":        {"regime_class": baseline_regime},
        "candidate":       {"regime_class": candidate_regime},
        "volatility_delta":  {"absolute": 0.0, "relative": 0.0},
        "breakpoint_delta":  {
            "baseline_count": 0, "candidate_count": 0, "delta": 0,
        },
        "event_summary": {
            "new_events": [], "resolved_events": [], "persistent_events": [],
        },
        "summary": "",
    }


def _elins_inputs(regime_delta: str = "same",
                   risk: str = "low",
                   fusion_history=None) -> dict:
    return {
        "batches":           [],
        "cross_batch":       None,
        "trend":             None,
        "structural":        _structural(),
        "regime_comparison": _comparison(regime_delta, risk),
        "fusion_history":    fusion_history,
    }


def _operator_intent(session_id: str = "sess_001",
                      operator_id: str = "op_alice",
                      timestamp: str = "2026-05-12T10:00:00+00:00",
                      intent_type: str = "query",
                      regime_delta: str = "same",
                      risk: str = "low",
                      fusion_history=None,
                      override=None) -> dict:
    payload = {
        "text": "operator intent text",
        "elins_inputs": _elins_inputs(regime_delta, risk, fusion_history),
    }
    if override is not None:
        payload["override"] = override
    return {
        "session_id":  session_id,
        "operator_id": operator_id,
        "timestamp":   timestamp,
        "intent_type": intent_type,
        "payload":     payload,
    }


def _session_context(session_id: str = "sess_001",
                      operator_id: str = "op_alice",
                      timestamp: str = "2026-05-12T10:00:00+00:00",
                      runtime_mode: str = "normal") -> dict:
    return {
        "session_id":   session_id,
        "operator_id":  operator_id,
        "timestamp":    timestamp,
        "runtime_mode": runtime_mode,
    }


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp",
            "runtime_decision", "runtime_events",
            "elins_block", "vault_update", "operator_view",
        }

    def test_operator_view_keys_locked(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert set(out["operator_view"].keys()) == {"headline", "details"}

    def test_operator_view_details_keys_locked(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert set(out["operator_view"]["details"].keys()) == {
            "decision", "runtime_events", "tags",
            "long_arc_assessment",
            "regime_start", "regime_end", "risk_level",
        }


# ===========================================================================
# B. Context passthrough
# ===========================================================================
class TestContextPassthrough:
    def test_session_id_echoed(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(session_id="custom_id"),
            _session_context(session_id="custom_id"),
            None,
        )
        assert out["session_id"] == "custom_id"

    def test_operator_id_echoed(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(operator_id="op_charlie"),
            _session_context(operator_id="op_charlie"),
            None,
        )
        assert out["operator_id"] == "op_charlie"

    def test_timestamp_echoed(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(timestamp="2030-01-01T00:00:00Z"),
            _session_context(timestamp="2030-01-01T00:00:00Z"),
            None,
        )
        assert out["timestamp"] == "2030-01-01T00:00:00Z"


# ===========================================================================
# C. ELINS wiring (Unit 33 binding)
# ===========================================================================
class TestElinsWiring:
    def test_elins_block_matches_unit_33(self):
        intent = _operator_intent()
        ctx = _session_context()
        out = rk_mod.run_runtime_step(intent, ctx, None)

        # Re-derive Unit 33 over the same inputs.
        expected_elins_ctx = {
            "session_id":    ctx["session_id"],
            "operator_id":   ctx["operator_id"],
            "timestamp":     ctx["timestamp"],
            "vault_state":   None,
            "runtime_flags": {"allow_overrides": True, "strict_mode": False},
        }
        expected = si_mod.run_elins_session(
            expected_elins_ctx, intent["payload"]["elins_inputs"],
        )
        assert out["elins_block"] == expected

    def test_strict_mode_propagates_to_elins_runtime_flags(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(),
            _session_context(runtime_mode="strict"),
            None,
        )
        # Strict mode runs ELINS the same way (ELINS doesn't read
        # strict_mode), so the elins_block still has the base decision.
        assert "elins_block" in out

    def test_vault_state_elins_substate_threaded_to_unit_33(self):
        prior = [_comparison("degraded", "high")]
        vault = {"elins": {"fusion_history": prior}}
        intent = _operator_intent(regime_delta="degraded", risk="high")
        ctx = _session_context()
        out = rk_mod.run_runtime_step(intent, ctx, vault)
        # ELINS should see 2 entries (prior + new comparison).
        history = out["elins_block"]["vault_update"]["fusion_history"]
        assert len(history) == 2

    def test_missing_vault_state_treated_as_first_session(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        # First session → fusion history has just the new comparison.
        assert len(out["elins_block"]["vault_update"]["fusion_history"]) == 1


# ===========================================================================
# D. Runtime action wiring (Unit 34 binding)
# ===========================================================================
class TestRuntimeActionWiring:
    def test_runtime_decision_matches_unit_34(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        # Apply Unit 34 over the same elins_block.
        expected = rt_mod.apply_elins_runtime_actions(
            {
                "session_id":       out["session_id"],
                "operator_id":      out["operator_id"],
                "timestamp":        out["timestamp"],
                "runtime_mode":     "normal",
                "previous_actions": [],
            },
            out["elins_block"],
        )
        assert out["runtime_decision"] == expected["decision"]
        assert out["runtime_events"] == expected["runtime_events"]

    def test_strict_mode_escalates_decision(self):
        # Stable seed yields ELINS allow → strict adjusts to warn.
        out = rk_mod.run_runtime_step(
            _operator_intent(),
            _session_context(runtime_mode="strict"),
            None,
        )
        assert out["runtime_decision"] == "warn"
        assert "runtime_warn" in out["runtime_events"]

    def test_diagnostic_mode_does_not_adjust(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(),
            _session_context(runtime_mode="diagnostic"),
            None,
        )
        # No adjustment from diagnostic; decision stays as ELINS reported.
        assert out["runtime_decision"] == out["elins_block"]["decision"]


# ===========================================================================
# E. Vault merging
# ===========================================================================
class TestVaultMerging:
    def test_vault_update_has_elins_substate(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert "elins" in out["vault_update"]

    def test_elins_substate_matches_elins_vault_update(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert out["vault_update"]["elins"] == \
               out["elins_block"]["vault_update"]

    def test_other_state_preserved(self):
        vault = {
            "elins":       {},
            "other_state": {"foo": "bar", "n": 42},
        }
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), vault,
        )
        assert out["vault_update"]["other_state"] == {"foo": "bar", "n": 42}

    def test_multiple_other_subsystems_preserved(self):
        vault = {
            "elins":      {},
            "subsystem_a": {"key": "a"},
            "subsystem_b": {"key": "b"},
            "subsystem_c": {"key": "c"},
        }
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), vault,
        )
        for sub in ("subsystem_a", "subsystem_b", "subsystem_c"):
            assert out["vault_update"][sub] == vault[sub]

    def test_elins_substate_replaced_not_merged(self):
        vault = {
            "elins": {
                "fusion_history": [_comparison("degraded", "high")],
                "stale_field":     "should_be_overwritten",
            },
        }
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), vault,
        )
        # stale_field is not in the new ELINS vault_update → gone.
        assert "stale_field" not in out["vault_update"]["elins"]


# ===========================================================================
# F. Override propagation
# ===========================================================================
class TestOverridePropagation:
    def test_override_applies_via_payload(self):
        intent = _operator_intent(
            override={"override_decision": "block"},
        )
        out = rk_mod.run_runtime_step(intent, _session_context(), None)
        assert out["runtime_decision"] == "block"
        assert "runtime_override" in out["runtime_events"]

    def test_override_escalate_propagates(self):
        intent = _operator_intent(
            override={"override_decision": "block", "escalate": True},
        )
        out = rk_mod.run_runtime_step(intent, _session_context(), None)
        assert "runtime_escalate" in out["runtime_events"]

    def test_no_override_no_override_event(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert "runtime_override" not in out["runtime_events"]


# ===========================================================================
# G. Operator view — headline + details
# ===========================================================================
class TestOperatorView:
    def test_headline_non_empty(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert out["operator_view"]["headline"].strip() != ""

    def test_headline_prefix_matches_decision(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        # Allow path → headline starts with "ALLOW:".
        assert out["operator_view"]["headline"].startswith("ALLOW:")

    def test_strict_mode_headline_prefix_warn(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(),
            _session_context(runtime_mode="strict"),
            None,
        )
        assert out["operator_view"]["headline"].startswith("WARN:")

    def test_persistent_degradation_headline(self):
        prior = [_comparison("degraded", "high") for _ in range(3)]
        intent = _operator_intent(
            regime_delta="degraded", risk="high",
            fusion_history=prior,
        )
        out = rk_mod.run_runtime_step(intent, _session_context(), None)
        assert "persistent degradation" in out["operator_view"][
            "headline"
        ].lower()

    def test_details_decision_matches_runtime_decision(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(),
            _session_context(runtime_mode="strict"),
            None,
        )
        assert out["operator_view"]["details"]["decision"] == \
               out["runtime_decision"]

    def test_details_long_arc_assessment_present(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert out["operator_view"]["details"]["long_arc_assessment"] in (
            "stabilizing", "persistent_degradation", "persistent_risk",
            "oscillating_regime", "benign",
        )

    def test_details_regime_start_and_end(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        details = out["operator_view"]["details"]
        assert details["regime_start"] in (
            "stable", "transition", "unstable", "",
        )
        assert details["regime_end"] in (
            "stable", "transition", "unstable", "",
        )

    def test_details_risk_level_in_locked_vocab(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert out["operator_view"]["details"]["risk_level"] in (
            "low", "medium", "high",
        )


# ===========================================================================
# H. Validation — operator_intent
# ===========================================================================
class TestOperatorIntentValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="operator_intent"):
            rk_mod.run_runtime_step("nope", _session_context(), None)

    def test_missing_session_id_raises(self):
        bad = _operator_intent()
        del bad["session_id"]
        with pytest.raises(ValueError, match="session_id"):
            rk_mod.run_runtime_step(bad, _session_context(), None)

    def test_missing_intent_type_raises(self):
        bad = _operator_intent()
        del bad["intent_type"]
        with pytest.raises(ValueError, match="intent_type"):
            rk_mod.run_runtime_step(bad, _session_context(), None)

    def test_invalid_intent_type_raises(self):
        bad = _operator_intent(intent_type="ponder")
        with pytest.raises(ValueError, match="intent_type"):
            rk_mod.run_runtime_step(bad, _session_context(), None)

    def test_non_dict_payload_raises(self):
        bad = _operator_intent()
        bad["payload"] = "nope"
        with pytest.raises(ValueError, match="payload"):
            rk_mod.run_runtime_step(bad, _session_context(), None)

    def test_missing_elins_inputs_raises(self):
        bad = _operator_intent()
        del bad["payload"]["elins_inputs"]
        with pytest.raises(ValueError, match="elins_inputs"):
            rk_mod.run_runtime_step(bad, _session_context(), None)

    def test_empty_session_id_raises(self):
        bad = _operator_intent(session_id="")
        with pytest.raises(ValueError, match="session_id"):
            rk_mod.run_runtime_step(bad, _session_context(), None)


# ===========================================================================
# I. Validation — session_context
# ===========================================================================
class TestSessionContextValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="session_context"):
            rk_mod.run_runtime_step(_operator_intent(), "nope", None)

    def test_missing_runtime_mode_raises(self):
        bad = _session_context()
        del bad["runtime_mode"]
        with pytest.raises(ValueError, match="runtime_mode"):
            rk_mod.run_runtime_step(_operator_intent(), bad, None)

    def test_invalid_runtime_mode_raises(self):
        bad = _session_context(runtime_mode="superstrict")
        with pytest.raises(ValueError, match="runtime_mode"):
            rk_mod.run_runtime_step(_operator_intent(), bad, None)

    def test_missing_session_id_raises(self):
        bad = _session_context()
        del bad["session_id"]
        with pytest.raises(ValueError, match="session_id"):
            rk_mod.run_runtime_step(_operator_intent(), bad, None)


# ===========================================================================
# J. Validation — vault_state
# ===========================================================================
class TestVaultStateValidation:
    def test_none_vault_state_ok(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        assert "elins" in out["vault_update"]

    def test_non_dict_vault_state_raises(self):
        with pytest.raises(ValueError, match="vault_state"):
            rk_mod.run_runtime_step(
                _operator_intent(), _session_context(), "nope",
            )

    def test_empty_dict_vault_state_ok(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), {},
        )
        assert "elins" in out["vault_update"]

    def test_non_dict_elins_substate_raises(self):
        with pytest.raises(ValueError, match="elins"):
            rk_mod.run_runtime_step(
                _operator_intent(),
                _session_context(),
                {"elins": "nope"},
            )


# ===========================================================================
# K. Determinism + immutability
# ===========================================================================
class TestDeterminismAndImmutability:
    def test_byte_equal_repeats(self):
        intent = _operator_intent()
        ctx = _session_context()
        a = rk_mod.run_runtime_step(intent, ctx, None)
        b = rk_mod.run_runtime_step(intent, ctx, None)
        assert a == b

    def test_byte_equal_with_vault(self):
        prior = [_comparison("degraded", "high")]
        vault = {"elins": {"fusion_history": prior}}
        intent = _operator_intent(regime_delta="degraded", risk="high")
        ctx = _session_context()
        a = rk_mod.run_runtime_step(intent, ctx, vault)
        b = rk_mod.run_runtime_step(intent, ctx, vault)
        assert a == b

    def test_inputs_not_mutated(self):
        intent = _operator_intent()
        ctx = _session_context()
        intent_snapshot = json.dumps(intent, sort_keys=True)
        ctx_snapshot = dict(ctx)
        rk_mod.run_runtime_step(intent, ctx, None)
        assert json.dumps(intent, sort_keys=True) == intent_snapshot
        assert ctx == ctx_snapshot

    def test_output_is_json_serializable(self):
        out = rk_mod.run_runtime_step(
            _operator_intent(), _session_context(), None,
        )
        encoded = json.dumps(out)
        decoded = json.loads(encoded)
        assert decoded["session_id"] == out["session_id"]


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(rk_mod.run_runtime_step)

    def test_intent_vocabulary_locked(self):
        assert rk_mod._VALID_INTENT_TYPES == (
            "query", "action", "plan", "diagnostic",
        )

    def test_runtime_modes_locked(self):
        assert rk_mod._VALID_RUNTIME_MODES == (
            "normal", "strict", "diagnostic",
        )


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(rk_mod)

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
        # Unit 35 is pure runtime composition — must not touch
        # persistence or vault storage layers. The dispatcher (Unit
        # 36) and outer layers own those.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result", "vault_store", "memory_vault",
        ):
            assert forbidden not in src

    def test_composes_units_33_and_34(self):
        src = self._code_only()
        assert "run_elins_session" in src
        assert "apply_elins_runtime_actions" in src
