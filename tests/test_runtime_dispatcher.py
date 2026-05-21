"""
Tests for Unit 36 — runtime dispatcher.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Context passthrough
    C. Model routing rules
    D. Kernel wiring (Unit 35 binding)
    E. Severity mapping
    F. UI response — headline / body
    G. UI response — tags (union + dedup)
    H. Runtime mode override via payload
    I. Validation
    J. Determinism + JSON safety
    K. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import runtime_dispatcher as rd_mod
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
                      runtime_mode=None,
                      metadata=None,
                      override=None) -> dict:
    payload = {
        "text": "operator intent text",
        "metadata": metadata or {},
        "elins_inputs": _elins_inputs(regime_delta, risk, fusion_history),
    }
    if runtime_mode is not None:
        payload["runtime_mode"] = runtime_mode
    if override is not None:
        payload["override"] = override
    return {
        "session_id":  session_id,
        "operator_id": operator_id,
        "timestamp":   timestamp,
        "intent_type": intent_type,
        "payload":     payload,
    }


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp",
            "model_route", "runtime", "ui_response",
        }

    def test_model_route_keys_locked(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert set(out["model_route"].keys()) == {"engine", "reason"}

    def test_ui_response_keys_locked(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert set(out["ui_response"].keys()) == {
            "headline", "body", "severity", "tags",
        }


# ===========================================================================
# B. Context passthrough
# ===========================================================================
class TestContextPassthrough:
    def test_session_id_echoed(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(session_id="custom_sess"), None,
        )
        assert out["session_id"] == "custom_sess"

    def test_operator_id_echoed(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(operator_id="op_charlie"), None,
        )
        assert out["operator_id"] == "op_charlie"

    def test_timestamp_echoed(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(timestamp="2030-01-01T00:00:00Z"), None,
        )
        assert out["timestamp"] == "2030-01-01T00:00:00Z"


# ===========================================================================
# C. Model routing rules
# ===========================================================================
class TestModelRouting:
    def test_diagnostic_routes_to_local(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="diagnostic"), None,
        )
        assert out["model_route"]["engine"] == "local"

    def test_plan_routes_to_claude(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="plan"), None,
        )
        assert out["model_route"]["engine"] == "claude"

    def test_query_routes_to_copilot(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="query"), None,
        )
        assert out["model_route"]["engine"] == "copilot"

    def test_action_routes_to_gemini(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="action"), None,
        )
        assert out["model_route"]["engine"] == "gemini"

    def test_metadata_does_not_affect_routing(self):
        # The locked routing table is keyed solely on intent_type;
        # metadata (e.g. a stale fast_path flag) must not override it.
        out_with_meta = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="query",
                              metadata={"fast_path": True}),
            None,
        )
        out_without_meta = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="query"), None,
        )
        assert out_with_meta["model_route"]["engine"] == \
               out_without_meta["model_route"]["engine"] == "copilot"

    def test_diagnostic_metadata_does_not_affect_routing(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(intent_type="diagnostic",
                              metadata={"fast_path": True}),
            None,
        )
        assert out["model_route"]["engine"] == "local"

    def test_engine_in_locked_vocab(self):
        for it in ("query", "action", "plan", "diagnostic"):
            out = rd_mod.dispatch_operator_intent(
                _operator_intent(intent_type=it), None,
            )
            assert out["model_route"]["engine"] in (
                "copilot", "claude", "gemini", "grok", "local",
            )

    def test_route_reason_non_empty(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert out["model_route"]["reason"].strip() != ""


# ===========================================================================
# D. Kernel wiring (Unit 35 binding)
# ===========================================================================
class TestKernelWiring:
    def test_runtime_matches_unit_35(self):
        intent = _operator_intent()
        expected_ctx = {
            "session_id":   intent["session_id"],
            "operator_id":  intent["operator_id"],
            "timestamp":    intent["timestamp"],
            "runtime_mode": "normal",
        }
        expected = rk_mod.run_runtime_step(intent, expected_ctx, None)
        out = rd_mod.dispatch_operator_intent(intent, None)
        assert out["runtime"] == expected

    def test_vault_state_threaded_through(self):
        prior = [_comparison("degraded", "high")]
        vault = {"elins": {"fusion_history": prior}}
        intent = _operator_intent(regime_delta="degraded", risk="high")
        out = rd_mod.dispatch_operator_intent(intent, vault)
        # Vault state survives one step of fusion-history extension.
        history = out["runtime"]["vault_update"]["elins"]["fusion_history"]
        assert len(history) == 2


# ===========================================================================
# E. Severity mapping
# ===========================================================================
class TestSeverityMapping:
    def test_allow_maps_to_info(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        # Stable seed → allow → info.
        assert out["ui_response"]["severity"] == "info"

    def test_strict_warn_maps_to_warning(self):
        # Strict adjusts the stable seed → warn → warning severity.
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(runtime_mode="strict"), None,
        )
        assert out["ui_response"]["severity"] == "warning"

    def test_block_maps_to_critical(self):
        # Persistent degradation history → block → critical.
        prior = [_comparison("degraded", "high") for _ in range(3)]
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(regime_delta="degraded", risk="high",
                              fusion_history=prior),
            None,
        )
        assert out["ui_response"]["severity"] == "critical"

    def test_severity_in_locked_vocab(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert out["ui_response"]["severity"] in (
            "info", "warning", "critical",
        )


# ===========================================================================
# F. UI response — headline / body
# ===========================================================================
class TestUIResponseHeadlineBody:
    def test_headline_from_operator_view(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert out["ui_response"]["headline"] == \
               out["runtime"]["operator_view"]["headline"]

    def test_body_non_empty(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert out["ui_response"]["body"].strip() != ""

    def test_body_mentions_long_arc(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert "long-arc" in out["ui_response"]["body"].lower() or \
               "long_arc" in out["ui_response"]["body"].lower()

    def test_body_mentions_risk(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert "risk" in out["ui_response"]["body"].lower()

    def test_body_event_count(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        # Should mention the count of runtime events.
        events_count = len(out["runtime"]["runtime_events"])
        assert str(events_count) in out["ui_response"]["body"]


# ===========================================================================
# G. UI response — tags
# ===========================================================================
class TestUIResponseTags:
    def test_tags_include_runtime_events(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        for ev in out["runtime"]["runtime_events"]:
            assert ev in out["ui_response"]["tags"]

    def test_tags_include_elins_tags(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        for t in out["runtime"]["elins_block"].get("tags", []):
            assert t in out["ui_response"]["tags"]

    def test_tags_alpha_sorted(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert out["ui_response"]["tags"] == \
               sorted(out["ui_response"]["tags"])

    def test_tags_deduped(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert len(out["ui_response"]["tags"]) == \
               len(set(out["ui_response"]["tags"]))

    def test_tags_is_list(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        assert isinstance(out["ui_response"]["tags"], list)


# ===========================================================================
# H. Runtime mode override via payload
# ===========================================================================
class TestRuntimeModeOverride:
    def test_default_runtime_mode_is_normal(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        # ELINS allow + normal mode → runtime decision allow.
        assert out["runtime"]["runtime_decision"] == "allow"

    def test_strict_runtime_mode_via_payload(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(runtime_mode="strict"), None,
        )
        # allow → warn under strict.
        assert out["runtime"]["runtime_decision"] == "warn"

    def test_diagnostic_runtime_mode_via_payload(self):
        out = rd_mod.dispatch_operator_intent(
            _operator_intent(runtime_mode="diagnostic"), None,
        )
        # Diagnostic doesn't adjust → still allow.
        assert out["runtime"]["runtime_decision"] == "allow"

    def test_invalid_runtime_mode_raises(self):
        with pytest.raises(ValueError, match="runtime_mode"):
            rd_mod.dispatch_operator_intent(
                _operator_intent(runtime_mode="superstrict"), None,
            )


# ===========================================================================
# I. Validation
# ===========================================================================
class TestValidation:
    def test_non_dict_intent_raises(self):
        with pytest.raises(ValueError, match="operator_intent"):
            rd_mod.dispatch_operator_intent("nope", None)

    def test_missing_session_id_raises(self):
        bad = _operator_intent()
        del bad["session_id"]
        with pytest.raises(ValueError, match="session_id"):
            rd_mod.dispatch_operator_intent(bad, None)

    def test_missing_payload_raises(self):
        bad = _operator_intent()
        del bad["payload"]
        with pytest.raises(ValueError, match="payload"):
            rd_mod.dispatch_operator_intent(bad, None)

    def test_non_dict_payload_raises(self):
        bad = _operator_intent()
        bad["payload"] = "nope"
        with pytest.raises(ValueError, match="payload"):
            rd_mod.dispatch_operator_intent(bad, None)

    def test_invalid_intent_type_propagates(self):
        # Unit 35 validates intent_type — dispatcher should surface it.
        bad = _operator_intent(intent_type="meditate")
        with pytest.raises(ValueError, match="intent_type"):
            rd_mod.dispatch_operator_intent(bad, None)

    def test_missing_elins_inputs_propagates(self):
        bad = _operator_intent()
        del bad["payload"]["elins_inputs"]
        with pytest.raises(ValueError, match="elins_inputs"):
            rd_mod.dispatch_operator_intent(bad, None)


# ===========================================================================
# J. Determinism + JSON safety
# ===========================================================================
class TestDeterminismAndJSONSafety:
    def test_byte_equal_repeats(self):
        intent = _operator_intent()
        a = rd_mod.dispatch_operator_intent(intent, None)
        b = rd_mod.dispatch_operator_intent(intent, None)
        assert a == b

    def test_byte_equal_with_vault(self):
        intent = _operator_intent()
        vault = {"elins": {"fusion_history": []}, "other": {"k": "v"}}
        a = rd_mod.dispatch_operator_intent(intent, vault)
        b = rd_mod.dispatch_operator_intent(intent, vault)
        assert a == b

    def test_output_is_json_serializable(self):
        out = rd_mod.dispatch_operator_intent(_operator_intent(), None)
        encoded = json.dumps(out)
        decoded = json.loads(encoded)
        assert decoded["session_id"] == out["session_id"]

    def test_input_not_mutated(self):
        intent = _operator_intent()
        snapshot = json.dumps(intent, sort_keys=True)
        rd_mod.dispatch_operator_intent(intent, None)
        assert json.dumps(intent, sort_keys=True) == snapshot


# ===========================================================================
# K. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(rd_mod.dispatch_operator_intent)

    def test_valid_engines_locked(self):
        assert rd_mod._VALID_ENGINES == (
            "copilot", "claude", "gemini", "grok", "local",
        )

    def test_severity_map_complete(self):
        assert rd_mod._DECISION_SEVERITY_MAP == {
            "allow": "info", "warn": "warning", "block": "critical",
        }

    def test_default_runtime_mode_locked(self):
        assert rd_mod._DEFAULT_RUNTIME_MODE == "normal"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(rd_mod)

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

    def test_no_actual_model_imports(self):
        # The dispatcher is a contract layer — must not invoke real
        # model SDKs or the existing kernel/router.
        src = self._code_only()
        for forbidden in (
            "openai", "anthropic", "google.generativeai",
            "intelligence_kernel", "perplexity_oracle", "model_router",
        ):
            assert forbidden not in src

    def test_no_persistence_imports(self):
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result", "vault_store", "memory_vault",
        ):
            assert forbidden not in src

    def test_composes_unit_35(self):
        src = self._code_only()
        assert "run_runtime_step" in src
