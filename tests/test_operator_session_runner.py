"""
Tests for Unit 39 — operator_session_runner.

Layered coverage (target ~35 tests):
    A. Top-level shape / locked keys
    B. Dispatch wiring (Unit 36 binding)
    C. Model wiring (Unit 38 binding)
    D. End-to-end intent-type happy paths
    E. Vault continuity roundtrip
    F. Validation
    G. Determinism + immutability
    H. JSON safety
    I. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import model_router as mr
import operator_session_runner as osr_mod
import runtime_dispatcher as rd_mod


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


def _operator_intent(
    session_id: str = "sess_001",
    operator_id: str = "op_alice",
    timestamp: str = "2026-05-12T10:00:00+00:00",
    intent_type: str = "query",
    regime_delta: str = "same",
    risk: str = "low",
    runtime_mode: str = "normal",
    fusion_history=None,
    override=None,
) -> dict:
    payload = {
        "text":         "operator intent text",
        "runtime_mode": runtime_mode,
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


@pytest.fixture(autouse=True)
def _reset_router():
    mr._reset_for_tests()
    yield
    mr._reset_for_tests()


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp",
            "runtime", "model", "vault_update",
        }

    def test_runtime_is_full_dispatch_output(self):
        # The "runtime" sub-object IS Unit 36's full output — must
        # contain its 5 locked top-level keys.
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert set(out["runtime"].keys()) == {
            "session_id", "operator_id", "timestamp",
            "model_route", "runtime", "ui_response",
        }

    def test_model_is_full_route_model_request_output(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert set(out["model"].keys()) == {
            "engine", "request", "response", "metadata",
        }

    def test_vault_update_is_dict(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert isinstance(out["vault_update"], dict)
        # Always carries the elins substate (Unit 35 guarantees this).
        assert "elins" in out["vault_update"]


# ===========================================================================
# B. Dispatch wiring (Unit 36 binding)
# ===========================================================================
class TestDispatchWiring:
    def test_session_id_echoed_from_intent(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(session_id="custom_sess"), None,
        )
        assert out["session_id"] == "custom_sess"

    def test_operator_id_echoed_from_intent(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(operator_id="op_zed"), None,
        )
        assert out["operator_id"] == "op_zed"

    def test_timestamp_echoed_from_intent(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(timestamp="2026-05-12T11:30:00+00:00"), None,
        )
        assert out["timestamp"] == "2026-05-12T11:30:00+00:00"

    def test_runtime_carries_model_route(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert "engine" in out["runtime"]["model_route"]
        assert "reason" in out["runtime"]["model_route"]

    def test_runtime_carries_ui_response(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert set(out["runtime"]["ui_response"].keys()) == {
            "headline", "body", "severity", "tags",
        }

    def test_runtime_inner_carries_elins_block(self):
        # result.runtime.runtime IS Unit 35's output — must carry the
        # full elins_block from Unit 33.
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert "elins_block" in out["runtime"]["runtime"]
        assert "fusion" in out["runtime"]["runtime"]["elins_block"]["elins"]


# ===========================================================================
# C. Model wiring (Unit 38 binding)
# ===========================================================================
class TestModelWiring:
    def test_engine_matches_dispatch_choice(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert out["model"]["engine"] == out["runtime"]["model_route"]["engine"]

    def test_request_has_model_id(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert "model_id" in out["model"]["request"]
        assert out["model"]["request"]["model_id"] in mr.SUPPORTED_MODELS

    def test_prompt_preview_capped_at_60(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert len(out["model"]["request"]["prompt_preview"]) <= 60

    def test_response_mock_when_no_provider_keys(self):
        # Tests run without provider env keys; route_request must
        # produce a mock payload, which Unit 38 echoes faithfully.
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert out["model"]["response"]["mock"] is True


# ===========================================================================
# D. End-to-end intent-type happy paths
# ===========================================================================
class TestIntentTypeHappyPaths:
    def test_query_routes_to_copilot_engine(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(intent_type="query"), None,
        )
        assert out["runtime"]["model_route"]["engine"] == "copilot"
        # copilot soft-maps to task "c" → openai:gpt-4o-mini.
        assert out["model"]["request"]["model_id"] == "openai:gpt-4o-mini"

    def test_plan_routes_to_claude_engine(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(intent_type="plan"), None,
        )
        assert out["runtime"]["model_route"]["engine"] == "claude"
        assert out["model"]["request"]["model_id"] == "openai:gpt-4o"

    def test_action_routes_to_gemini_engine(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(intent_type="action"), None,
        )
        assert out["runtime"]["model_route"]["engine"] == "gemini"
        # gemini soft-maps to task "ELINS" → openai:gpt-4o.
        assert out["model"]["request"]["model_id"] == "openai:gpt-4o"

    def test_diagnostic_routes_to_local_hard_pin(self):
        out = osr_mod.run_operator_session_step(
            _operator_intent(intent_type="diagnostic"), None,
        )
        assert out["runtime"]["model_route"]["engine"] == "local"
        # local hard-pins (OS policy — diagnostic stays on-device).
        assert out["model"]["request"]["model_id"] == mr.LOCAL_MODEL_ID

    def test_diagnostic_ignores_founder_default(self):
        mr.set_founder_default_model("anthropic:claude-3.7")
        try:
            out = osr_mod.run_operator_session_step(
                _operator_intent(intent_type="diagnostic"), None,
            )
            # Hard-pin must win.
            assert out["model"]["request"]["model_id"] == mr.LOCAL_MODEL_ID
        finally:
            mr.set_founder_default_model(None)


# ===========================================================================
# E. Vault continuity roundtrip
# ===========================================================================
class TestVaultContinuity:
    def test_cold_start_vault_update_has_elins(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert "elins" in out["vault_update"]
        assert "fusion_history" in out["vault_update"]["elins"]

    def test_vault_update_matches_runtime_inner(self):
        # Top-level vault_update is a pass-through of Unit 35's merged
        # output — must equal result.runtime.runtime.vault_update.
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        assert (
            out["vault_update"]
            == out["runtime"]["runtime"]["vault_update"]
        )

    def test_second_step_extends_fusion_history(self):
        first = osr_mod.run_operator_session_step(_operator_intent(), None)
        first_hist = first["vault_update"]["elins"]["fusion_history"]
        # Feed the prior vault back in for step 2.
        second = osr_mod.run_operator_session_step(
            _operator_intent(timestamp="2026-05-12T11:00:00+00:00"),
            first["vault_update"],
        )
        second_hist = second["vault_update"]["elins"]["fusion_history"]
        assert len(second_hist) == len(first_hist) + 1

    def test_non_elins_vault_keys_preserved(self):
        prior_vault = {
            "elins": {"fusion_history": []},
            "other_substate": {"foo": "bar"},
        }
        out = osr_mod.run_operator_session_step(
            _operator_intent(), prior_vault,
        )
        assert out["vault_update"]["other_substate"] == {"foo": "bar"}


# ===========================================================================
# F. Validation
# ===========================================================================
class TestValidation:
    def test_intent_none_rejected(self):
        with pytest.raises(ValueError, match="operator_intent"):
            osr_mod.run_operator_session_step(None, None)

    def test_intent_list_rejected(self):
        with pytest.raises(ValueError, match="operator_intent"):
            osr_mod.run_operator_session_step([1, 2, 3], None)

    def test_vault_state_list_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            osr_mod.run_operator_session_step(_operator_intent(), [])

    def test_vault_state_string_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            osr_mod.run_operator_session_step(_operator_intent(), "x")

    def test_downstream_unknown_intent_type_propagates(self):
        intent = _operator_intent()
        intent["intent_type"] = "not_a_real_type"
        with pytest.raises(ValueError):
            osr_mod.run_operator_session_step(intent, None)

    def test_downstream_missing_elins_inputs_propagates(self):
        intent = _operator_intent()
        del intent["payload"]["elins_inputs"]
        with pytest.raises(ValueError):
            osr_mod.run_operator_session_step(intent, None)


# ===========================================================================
# G. Determinism + immutability
# ===========================================================================
class TestDeterminism:
    def test_repeatable_dispatch_for_same_input(self):
        a = osr_mod.run_operator_session_step(_operator_intent(), None)
        b = osr_mod.run_operator_session_step(_operator_intent(), None)
        # route_request stamps time.time() so we can't compare ts.
        assert a["runtime"] == b["runtime"]
        assert a["model"]["engine"] == b["model"]["engine"]
        assert a["model"]["request"] == b["model"]["request"]
        assert a["vault_update"] == b["vault_update"]

    def test_intent_not_mutated(self):
        intent = _operator_intent()
        snap = json.dumps(intent, sort_keys=True)
        osr_mod.run_operator_session_step(intent, None)
        assert json.dumps(intent, sort_keys=True) == snap

    def test_vault_state_not_mutated(self):
        vault = {"elins": {"fusion_history": []}, "extra": 1}
        snap = json.dumps(vault, sort_keys=True)
        osr_mod.run_operator_session_step(_operator_intent(), vault)
        assert json.dumps(vault, sort_keys=True) == snap


# ===========================================================================
# H. JSON safety
# ===========================================================================
class TestJsonSafety:
    def test_output_json_roundtrip_cold_start(self):
        out = osr_mod.run_operator_session_step(_operator_intent(), None)
        s = json.dumps(out)
        # Loaded value compares equal even after float round-trips.
        assert json.loads(s) == out

    def test_output_json_roundtrip_with_prior_vault(self):
        first = osr_mod.run_operator_session_step(_operator_intent(), None)
        second = osr_mod.run_operator_session_step(
            _operator_intent(timestamp="2026-05-12T11:00:00+00:00"),
            first["vault_update"],
        )
        s = json.dumps(second)
        assert json.loads(s) == second


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_run_operator_session_step_exported(self):
        assert hasattr(osr_mod, "run_operator_session_step")
        assert callable(osr_mod.run_operator_session_step)

    def test_signature_locked(self):
        sig = inspect.signature(osr_mod.run_operator_session_step)
        assert list(sig.parameters.keys()) == [
            "operator_intent", "vault_state",
        ]

    def test_imports_only_dispatcher_and_router(self):
        src = inspect.getsource(osr_mod)
        # Unit 39 must only know about the two surfaces below it.
        assert "from runtime_dispatcher import" in src
        assert "from model_router import" in src
        # No direct ELINS or kernel imports — those leak through the
        # dispatcher.
        for forbidden in (
            "from runtime_kernel",
            "from elins_session_integrator",
            "from elins_runtime_actions",
        ):
            assert forbidden not in src

    def test_no_io_imports(self):
        src = inspect.getsource(osr_mod)
        for forbidden in (
            "import requests", "import httpx",
            "open(", "subprocess",
            "asyncio.open_connection",
        ):
            assert forbidden not in src
