"""
Tests for Unit 40 — session_loop façade.

Layered coverage (target ~40 tests):
    A. start_session — shape, validation, determinism (via patch)
    B. step_session — single-step shape + Unit 39 binding
    C. Vault continuity across multiple steps
    D. History — content, ordering, append semantics
    E. Engine + decision propagation
    F. intent_type vocabulary + validation
    G. session_state validation
    H. Immutability (input session_state never mutated)
    I. Monkey-patch surface (_now + _make_session_id + _default_elins_inputs)
    J. JSON safety + source-code purity
"""
from __future__ import annotations

import inspect
import json

import pytest

import model_router as mr
import runtime_persistence as rp_mod
import session_loop as sl_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset_router_and_clock(monkeypatch):
    """Pin _now to a fixed ISO timestamp + give each test a fresh
    session_id sequence. Resets the router and runtime_persistence
    between tests so engine preferences + persisted vaults don't
    leak across cases (v61 / Unit 43 wired persistence into the
    loop)."""
    counter = {"n": 0}

    def fake_now():
        return f"2026-05-12T10:00:{counter['n']:02d}+00:00"

    def fake_make_session_id():
        return f"sess-test-{counter['n']:03d}"

    def step_clock():
        counter["n"] += 1

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)
    # Each call to step_session bumps the clock; tests that need to
    # bump manually can call ``step_clock()`` through this fixture.
    monkeypatch.setattr(sl_mod, "_step_clock_for_tests", step_clock,
                        raising=False)

    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield counter
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


@pytest.fixture
def stepped_clock(_reset_router_and_clock, monkeypatch):
    """Variant where _now advances by one second per call so multi-step
    tests get distinct timestamps."""
    counter = _reset_router_and_clock

    def fake_now():
        counter["n"] += 1
        return f"2026-05-12T10:00:{counter['n']:02d}+00:00"

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    return counter


# ===========================================================================
# A. start_session — shape, validation, determinism
# ===========================================================================
class TestStartSession:
    def test_returns_locked_keys(self):
        state = sl_mod.start_session("op_alice")
        assert set(state.keys()) == {
            "session_id", "operator_id", "vault_state", "history",
        }

    def test_session_id_from_factory(self):
        state = sl_mod.start_session("op_alice")
        assert state["session_id"] == "sess-test-000"

    def test_operator_id_echoed(self):
        state = sl_mod.start_session("op_alice")
        assert state["operator_id"] == "op_alice"

    def test_vault_state_empty(self):
        state = sl_mod.start_session("op_alice")
        assert state["vault_state"] == {}

    def test_history_empty(self):
        state = sl_mod.start_session("op_alice")
        assert state["history"] == []

    def test_rejects_empty_operator_id(self):
        with pytest.raises(ValueError, match="operator_id"):
            sl_mod.start_session("")

    def test_rejects_non_string_operator_id(self):
        with pytest.raises(ValueError, match="operator_id"):
            sl_mod.start_session(42)

    def test_rejects_none_operator_id(self):
        with pytest.raises(ValueError, match="operator_id"):
            sl_mod.start_session(None)


# ===========================================================================
# B. step_session — single-step shape + Unit 39 binding
# ===========================================================================
class TestStepSessionShape:
    def test_returns_two_keys(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "do a thing")
        assert set(out.keys()) == {"session_state", "step_result"}

    def test_step_result_is_full_unit39_output(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "do a thing")
        assert set(out["step_result"].keys()) == {
            "session_id", "operator_id", "timestamp",
            "runtime", "model", "vault_update",
        }

    def test_step_result_session_id_matches_state(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "do a thing")
        assert out["step_result"]["session_id"] == state["session_id"]

    def test_step_result_operator_id_matches_state(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "do a thing")
        assert out["step_result"]["operator_id"] == "op_alice"

    def test_session_state_carries_session_id(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "do a thing")
        assert out["session_state"]["session_id"] == state["session_id"]


# ===========================================================================
# C. Vault continuity across multiple steps
# ===========================================================================
class TestVaultContinuity:
    def test_vault_state_populated_after_first_step(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "first step")
        assert "elins" in out["session_state"]["vault_state"]

    def test_fusion_history_grows_per_step(self):
        state = sl_mod.start_session("op_alice")
        s1 = sl_mod.step_session(state, "step 1")
        s2 = sl_mod.step_session(s1["session_state"], "step 2")
        s3 = sl_mod.step_session(s2["session_state"], "step 3")
        h1 = s1["session_state"]["vault_state"]["elins"]["fusion_history"]
        h2 = s2["session_state"]["vault_state"]["elins"]["fusion_history"]
        h3 = s3["session_state"]["vault_state"]["elins"]["fusion_history"]
        assert len(h1) == 1
        assert len(h2) == 2
        assert len(h3) == 3

    def test_vault_state_passes_through_step39(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "step 1")
        # session_state.vault_state must equal step_result.vault_update.
        assert (
            out["session_state"]["vault_state"]
            == out["step_result"]["vault_update"]
        )


# ===========================================================================
# D. History — content, ordering, append semantics
# ===========================================================================
class TestHistory:
    def test_history_appended_after_first_step(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "first step")
        assert len(out["session_state"]["history"]) == 1

    def test_history_entry_keys_locked(self):
        # v64 / Unit 65 — entry shape is REQUIRED-keys-locked, not
        # exact-keys-locked. The v59 contract still mandates the 5
        # original keys; v65 adds an optional ``provider_error`` that
        # only appears when the real-HTTP path falls back to mock.
        # Use ``<=`` (subset) rather than ``==`` so the optional
        # field doesn't trip the assertion on real provider failures.
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "first step")
        entry = out["session_state"]["history"][0]
        required = {
            "timestamp", "intent_type", "text",
            "runtime_decision", "engine",
        }
        assert required <= set(entry.keys())
        # And the only allowed extra is provider_error (v65-additive).
        assert set(entry.keys()) <= required | {"provider_error"}

    def test_history_entry_carries_text(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "make it so")
        assert out["session_state"]["history"][0]["text"] == "make it so"

    def test_history_entry_carries_intent_type(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "go", intent_type="plan")
        assert out["session_state"]["history"][0]["intent_type"] == "plan"

    def test_history_ordered_by_step(self):
        state = sl_mod.start_session("op_alice")
        s1 = sl_mod.step_session(state, "one")
        s2 = sl_mod.step_session(s1["session_state"], "two")
        s3 = sl_mod.step_session(s2["session_state"], "three")
        texts = [e["text"] for e in s3["session_state"]["history"]]
        assert texts == ["one", "two", "three"]


# ===========================================================================
# E. Engine + decision propagation
# ===========================================================================
class TestEnginePropagation:
    def test_query_records_copilot_engine(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?", intent_type="query")
        assert out["session_state"]["history"][0]["engine"] == "copilot"

    def test_plan_records_claude_engine(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?", intent_type="plan")
        assert out["session_state"]["history"][0]["engine"] == "claude"

    def test_action_records_gemini_engine(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?", intent_type="action")
        assert out["session_state"]["history"][0]["engine"] == "gemini"

    def test_diagnostic_records_local_engine(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?", intent_type="diagnostic")
        assert out["session_state"]["history"][0]["engine"] == "local"

    def test_runtime_decision_in_history(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?")
        decision = out["session_state"]["history"][0]["runtime_decision"]
        assert decision in {"allow", "warn", "block"}


# ===========================================================================
# F. intent_type vocabulary + validation
# ===========================================================================
class TestIntentTypeValidation:
    def test_default_is_query(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "?")
        assert out["session_state"]["history"][0]["intent_type"] == "query"

    def test_all_valid_types_accepted(self):
        for it in ("query", "action", "plan", "diagnostic"):
            state = sl_mod.start_session("op_alice")
            sl_mod.step_session(state, "?", intent_type=it)  # no raise

    def test_unknown_type_rejected(self):
        state = sl_mod.start_session("op_alice")
        with pytest.raises(ValueError, match="intent_type"):
            sl_mod.step_session(state, "?", intent_type="hallucinate")

    def test_empty_type_rejected(self):
        state = sl_mod.start_session("op_alice")
        with pytest.raises(ValueError, match="intent_type"):
            sl_mod.step_session(state, "?", intent_type="")


# ===========================================================================
# G. session_state validation
# ===========================================================================
class TestSessionStateValidation:
    def test_non_dict_rejected(self):
        with pytest.raises(ValueError, match="session_state"):
            sl_mod.step_session(None, "?")

    def test_missing_session_id_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            sl_mod.step_session(
                {"operator_id": "x", "vault_state": {}, "history": []},
                "?",
            )

    def test_missing_vault_state_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            sl_mod.step_session(
                {"session_id": "s", "operator_id": "x", "history": []},
                "?",
            )

    def test_missing_history_rejected(self):
        with pytest.raises(ValueError, match="history"):
            sl_mod.step_session(
                {"session_id": "s", "operator_id": "x", "vault_state": {}},
                "?",
            )

    def test_non_string_text_rejected(self):
        state = sl_mod.start_session("op_alice")
        with pytest.raises(ValueError, match="text"):
            sl_mod.step_session(state, 42)


# ===========================================================================
# H. Immutability — input session_state never mutated
# ===========================================================================
class TestImmutability:
    def test_start_session_returns_independent_state(self):
        a = sl_mod.start_session("op_alice")
        b = sl_mod.start_session("op_alice")
        a["history"].append("contamination")
        assert b["history"] == []

    def test_step_session_does_not_mutate_input(self):
        state = sl_mod.start_session("op_alice")
        snap = json.dumps(state, sort_keys=True)
        sl_mod.step_session(state, "step")
        assert json.dumps(state, sort_keys=True) == snap

    def test_step_session_returns_new_history_list(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "step")
        # Old list still empty; new list has one entry.
        assert state["history"] == []
        assert len(out["session_state"]["history"]) == 1
        assert out["session_state"]["history"] is not state["history"]


# ===========================================================================
# I. Monkey-patch surface
# ===========================================================================
class TestPatchSurface:
    def test_now_patchable(self, monkeypatch):
        monkeypatch.setattr(sl_mod, "_now",
                            lambda: "2099-12-31T23:59:59+00:00")
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "step")
        assert (
            out["session_state"]["history"][0]["timestamp"]
            == "2099-12-31T23:59:59+00:00"
        )

    def test_make_session_id_patchable(self, monkeypatch):
        monkeypatch.setattr(sl_mod, "_make_session_id",
                            lambda: "sess-test-pinned")
        state = sl_mod.start_session("op_alice")
        assert state["session_id"] == "sess-test-pinned"

    def test_default_elins_inputs_returns_fresh_dict(self):
        a = sl_mod._default_elins_inputs()
        b = sl_mod._default_elins_inputs()
        a["batches"].append("contamination")
        assert b["batches"] == []

    def test_default_elins_inputs_satisfies_unit33_contract(self):
        inputs = sl_mod._default_elins_inputs()
        # Unit 33 requires structural + regime_comparison (with the
        # Unit 29 keys: regime_delta, risk_assessment, baseline,
        # candidate).
        assert "structural" in inputs
        assert "regime_comparison" in inputs
        rc = inputs["regime_comparison"]
        for k in ("regime_delta", "risk_assessment", "baseline", "candidate"):
            assert k in rc


# ===========================================================================
# J. JSON safety + source-code purity
# ===========================================================================
class TestJsonSafetyAndPurity:
    def test_session_state_json_roundtrip(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "step")
        s = json.dumps(out["session_state"])
        assert json.loads(s) == out["session_state"]

    def test_full_step_output_json_roundtrip(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "step")
        s = json.dumps(out)
        assert json.loads(s) == out

    def test_no_persistence_imports(self):
        src = inspect.getsource(sl_mod)
        for forbidden in (
            "import requests", "import httpx",
            "open(", "subprocess",
            "asyncio.open_connection",
            "import sqlite3", "import pickle",
        ):
            assert forbidden not in src, (
                f"session_loop must not use {forbidden!r}"
            )

    def test_imports_only_runner_persistence_and_stdlib(self):
        # v61 / Unit 43 expanded the lock from "runner + stdlib" to
        # "runner + persistence + stdlib". The session_loop façade is
        # the natural integration point for vault/session storage
        # because it already owns the session_state shape; pushing
        # persistence into a lower layer would force every caller of
        # Unit 39 to handle persistence separately. Adding runtime_http
        # / web client / desktop / phone here would be a violation.
        src = inspect.getsource(sl_mod)
        assert "from operator_session_runner import" in src
        assert "import runtime_persistence" in src
        # No direct dispatcher / kernel / router knowledge.
        for forbidden in (
            "from runtime_kernel",
            "from runtime_dispatcher",
            "from model_router",
            "from elins_session_integrator",
            "from elins_runtime_actions",
        ):
            assert forbidden not in src

    def test_public_api_exported(self):
        assert hasattr(sl_mod, "start_session")
        assert hasattr(sl_mod, "step_session")
        assert callable(sl_mod.start_session)
        assert callable(sl_mod.step_session)
