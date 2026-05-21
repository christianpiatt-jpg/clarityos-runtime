"""
Tests for v61 / Unit 43 — persistence-integrated runtime.

Validates that ``session_loop.start_session`` + ``session_loop.step_session``
correctly hydrate / persist via ``runtime_persistence``, and that
``runtime_http`` honours ``resume=true`` on ``/operator/session/start``.

"Restart" is simulated by clearing ``session_loop``'s upstream
in-memory state while leaving ``runtime_persistence`` populated —
the same disk-survives-process-exit semantics, without actually
restarting a process. We use the in-memory backend throughout; the
file backend is exercised in ``test_runtime_persistence.py``.

Layered coverage (target ~40 tests):
    A. start_session hydrates vault from persistence
    B. start_session saves the new session immediately
    C. step_session persists vault per step
    D. step_session persists session per step
    E. Cross-session continuity via vault (new session, same operator)
    F. HTTP /start with resume=true
    G. HTTP /start resume ownership check
    H. Immutability + JSON safety under persistence
    I. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import session_loop as sl_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset_all(monkeypatch):
    """Each test starts clean: empty router, empty persistence dicts,
    and pinned clock + session_id factory. Both counters tick
    independently so two start_session calls in a row produce two
    distinct session_ids (the cross-session-continuity tests below
    need that; the v40 single-counter fixture was fine when every
    test only minted one session)."""
    clock_counter = {"n": 0}
    sid_counter   = {"n": 0}

    def fake_now():
        clock_counter["n"] += 1
        return f"2026-05-12T10:00:{clock_counter['n']:02d}+00:00"

    def fake_make_session_id():
        sid_counter["n"] += 1
        return f"sess-int-{sid_counter['n']:03d}"

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)
    monkeypatch.delenv("CLARITYOS_RUNTIME_STORE_DIR", raising=False)
    rp_mod.reload_backend()
    rp_mod._reset_for_tests()
    mr._reset_for_tests()
    yield
    rp_mod._reset_for_tests()
    mr._reset_for_tests()


@pytest.fixture
def client():
    """Private FastAPI app with only the runtime router mounted."""
    app = FastAPI()
    app.include_router(rh_mod.runtime_router)
    # v65 / Unit 68 — dep override so the v61 persistence-integration
    # tests don't need to plumb X-Session-ID; auth coverage is in
    # test_operator_session_auth.py. The override returns the operator
    # whose name appears in the test's POST body so ownership checks
    # match (most tests use op_alice; cross-operator tests swap
    # the cell value mid-flight if needed).
    from contextvars import ContextVar
    _override = {"op": "op_alice"}
    app.dependency_overrides[rh_mod.require_operator] = lambda: _override["op"]
    app.state.override_cell = _override  # type: ignore[attr-defined]
    return TestClient(app)


# ===========================================================================
# A. start_session hydrates vault from persistence
# ===========================================================================
class TestVaultHydration:
    def test_cold_start_vault_empty(self):
        state = sl_mod.start_session("op_alice")
        assert state["vault_state"] == {}

    def test_warm_start_hydrates_from_prior_vault(self):
        # Seed a vault directly through persistence.
        prior_vault = {
            "elins": {
                "last_fusion":    {"timestamp": "2026-05-12T09:00:00+00:00"},
                "last_long_arc":  None,
                "fusion_history": [{"step": 1}],
            },
        }
        rp_mod.save_vault("op_alice", prior_vault)

        state = sl_mod.start_session("op_alice")
        assert state["vault_state"] == prior_vault

    def test_each_start_mints_fresh_session_id(self):
        # Even with a hydrated vault, session_id must be fresh.
        rp_mod.save_vault("op_alice", {"elins": {"fusion_history": []}})
        s1 = sl_mod.start_session("op_alice")
        s2 = sl_mod.start_session("op_alice")
        assert s1["session_id"] != s2["session_id"]

    def test_history_always_empty_on_start(self):
        # History is per-session; a hydrated vault must not bring
        # someone else's history with it.
        rp_mod.save_vault("op_alice", {
            "elins": {"fusion_history": [{"step": 1}]},
        })
        state = sl_mod.start_session("op_alice")
        assert state["history"] == []

    def test_operator_isolation(self):
        rp_mod.save_vault("op_alice", {
            "elins": {"fusion_history": [{"step": 1}]},
        })
        rp_mod.save_vault("op_bob", {
            "elins": {"fusion_history": [{"step": 999}]},
        })
        alice = sl_mod.start_session("op_alice")
        bob   = sl_mod.start_session("op_bob")
        assert alice["vault_state"]["elins"]["fusion_history"] == [{"step": 1}]
        assert bob["vault_state"]["elins"]["fusion_history"] == [{"step": 999}]


# ===========================================================================
# B. start_session saves the new session immediately
# ===========================================================================
class TestStartSavesSession:
    def test_session_loadable_after_start(self):
        state = sl_mod.start_session("op_alice")
        loaded = rp_mod.load_session(state["session_id"])
        assert loaded is not None
        assert loaded["operator_id"] == "op_alice"

    def test_loaded_session_matches_returned_state(self):
        state = sl_mod.start_session("op_alice")
        loaded = rp_mod.load_session(state["session_id"])
        assert loaded["session_id"]  == state["session_id"]
        assert loaded["operator_id"] == state["operator_id"]
        assert loaded["history"]     == []


# ===========================================================================
# C. step_session persists vault per step
# ===========================================================================
class TestStepPersistsVault:
    def test_vault_saved_after_step(self):
        state = sl_mod.start_session("op_alice")
        sl_mod.step_session(state, "step one")
        vault = rp_mod.load_vault("op_alice")
        assert vault is not None
        assert "elins" in vault

    def test_vault_grows_across_steps(self):
        state = sl_mod.start_session("op_alice")
        s1 = sl_mod.step_session(state, "one")
        s2 = sl_mod.step_session(s1["session_state"], "two")
        s3 = sl_mod.step_session(s2["session_state"], "three")
        vault = rp_mod.load_vault("op_alice")
        history = vault["elins"]["fusion_history"]
        assert len(history) == 3

    def test_two_operators_have_separate_vaults(self):
        # v64 / Unit 64 update: each step_session now reloads vault
        # + session from persistence before applying, so even
        # passing stale ``a`` to a second step produces correct
        # extension (the function reloads, sees the persisted
        # post-a-1 state, then applies a-2). The original v61 test
        # carefully chained ``a1["session_state"]`` as a workaround
        # for the v43 race; under v64 the race is gone, so this
        # test now reads more naturally and still passes.
        a = sl_mod.start_session("op_alice")
        b = sl_mod.start_session("op_bob")
        a1 = sl_mod.step_session(a, "a-1")
        # Intentionally feed stale ``a`` (NOT a1["session_state"]) —
        # v64 reload makes this safe.
        a2 = sl_mod.step_session(a, "a-2")
        b1 = sl_mod.step_session(b, "b-1")
        alice_vault = rp_mod.load_vault("op_alice")
        bob_vault   = rp_mod.load_vault("op_bob")
        assert len(alice_vault["elins"]["fusion_history"]) == 2
        assert len(bob_vault["elins"]["fusion_history"])   == 1


# ===========================================================================
# D. step_session persists session per step
# ===========================================================================
class TestStepPersistsSession:
    def test_session_history_loadable_after_step(self):
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "one")
        loaded = rp_mod.load_session(state["session_id"])
        assert loaded["history"] == out["session_state"]["history"]

    def test_session_load_returns_latest_after_multiple_steps(self):
        state = sl_mod.start_session("op_alice")
        s1 = sl_mod.step_session(state, "one")
        s2 = sl_mod.step_session(s1["session_state"], "two")
        loaded = rp_mod.load_session(state["session_id"])
        assert len(loaded["history"]) == 2
        assert loaded["history"][-1]["text"] == "two"


# ===========================================================================
# E. Cross-session continuity via vault (the resume story)
# ===========================================================================
class TestCrossSessionContinuity:
    def test_new_session_inherits_prior_vault(self):
        # Operator's first session — populates the vault.
        first = sl_mod.start_session("op_alice")
        sl_mod.step_session(first, "session-one step")
        # Operator returns later — different session, same vault.
        second = sl_mod.start_session("op_alice")
        # Continuity: vault is non-empty because the prior session
        # wrote to it; history is empty because it's a new session.
        assert second["vault_state"]["elins"]["fusion_history"]
        assert second["history"] == []

    def test_fusion_history_carries_across_sessions(self):
        first = sl_mod.start_session("op_alice")
        s1 = sl_mod.step_session(first, "session-one-step-1")
        s2 = sl_mod.step_session(s1["session_state"], "session-one-step-2")
        second = sl_mod.start_session("op_alice")
        # Two fusions from session one, plus zero from session two so far.
        assert len(second["vault_state"]["elins"]["fusion_history"]) == 2

    def test_step_in_second_session_extends_inherited_history(self):
        first = sl_mod.start_session("op_alice")
        sl_mod.step_session(first, "session-one")
        second = sl_mod.start_session("op_alice")
        s2 = sl_mod.step_session(second, "session-two")
        # Vault now holds both sessions' contributions.
        vault = rp_mod.load_vault("op_alice")
        assert len(vault["elins"]["fusion_history"]) == 2


# ===========================================================================
# F. HTTP /start with resume=true
# ===========================================================================
class TestHttpResume:
    def test_resume_returns_prior_session(self, client):
        # Establish a session via /start, take one step.
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        # Resume the session — must match what's on disk after the step.
        resumed = client.post(
            "/operator/session/start",
            json={
                "operator_id": "op_alice",
                "resume":      True,
                "session_id":  s0["session_id"],
            },
        ).json()["session_state"]
        assert resumed["session_id"] == s0["session_id"]
        assert len(resumed["history"]) == 1
        assert resumed["history"][0]["text"] == "one"

    def test_resume_miss_falls_back_to_fresh(self, client):
        # session_id doesn't exist — resume falls back silently.
        r = client.post(
            "/operator/session/start",
            json={
                "operator_id": "op_alice",
                "resume":      True,
                "session_id":  "sess-nonexistent",
            },
        ).json()
        assert "session_state" in r
        assert r["session_state"]["operator_id"] == "op_alice"
        # Fresh session: empty history.
        assert r["session_state"]["history"] == []
        # And the session_id is freshly minted, NOT the missing one.
        assert r["session_state"]["session_id"] != "sess-nonexistent"

    def test_resume_false_ignores_session_id(self, client):
        # Even with a valid session on disk, resume=false starts fresh.
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/start",
            json={
                "operator_id": "op_alice",
                "resume":      False,
                "session_id":  s0["session_id"],
            },
        ).json()
        # Fresh session minted, not the original.
        assert r["session_state"]["session_id"] != s0["session_id"]

    def test_resume_without_session_id_is_fresh(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice", "resume": True},
        ).json()
        assert r["session_state"]["history"] == []


# ===========================================================================
# G. HTTP /start resume ownership check
# ===========================================================================
class TestResumeOwnership:
    def test_resume_rejects_other_operators_session(self, client):
        # v68 update — auth dep override returns the current cell
        # value. Swap mid-test so the two POSTs happen as different
        # authed operators.
        cell = client._app.state.override_cell  # type: ignore[attr-defined]
        cell["op"] = "op_alice"
        alice_s = client.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
        ).json()["session_state"]
        # Swap auth to Bob and attempt resume of Alice's session.
        cell["op"] = "op_bob"
        bob_r = client.post(
            "/operator/session/start",
            json={
                "operator_id": "ignored",
                "resume":      True,
                "session_id":  alice_s["session_id"],
            },
        ).json()
        # Falls back to a fresh session for Bob (silent miss).
        assert bob_r["session_state"]["operator_id"] == "op_bob"
        assert bob_r["session_state"]["session_id"] != alice_s["session_id"]

    def test_resume_with_malformed_session_id_returns_400(self, client):
        # Path-traversal style — rejected at the persistence layer,
        # surfaced to the client as 400 rather than silent fallback
        # so the client knows the input was bad.
        r = client.post(
            "/operator/session/start",
            json={
                "operator_id": "op_alice",
                "resume":      True,
                "session_id":  "../etc/passwd",
            },
        )
        assert r.status_code == 400


# ===========================================================================
# H. Immutability + JSON safety under persistence
# ===========================================================================
class TestImmutabilityAndJsonSafety:
    def test_input_state_not_mutated_by_step(self):
        state = sl_mod.start_session("op_alice")
        snap = json.dumps(state, sort_keys=True)
        sl_mod.step_session(state, "step")
        assert json.dumps(state, sort_keys=True) == snap

    def test_loaded_session_is_json_safe(self):
        state = sl_mod.start_session("op_alice")
        sl_mod.step_session(state, "step")
        loaded = rp_mod.load_session(state["session_id"])
        s = json.dumps(loaded)
        assert json.loads(s) == loaded

    def test_loaded_vault_is_json_safe(self):
        state = sl_mod.start_session("op_alice")
        sl_mod.step_session(state, "step")
        loaded = rp_mod.load_vault("op_alice")
        s = json.dumps(loaded)
        assert json.loads(s) == loaded


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_session_loop_imports_persistence(self):
        # The whole point of v61: persistence is now wired in.
        src = inspect.getsource(sl_mod)
        assert "import runtime_persistence" in src

    def test_runtime_http_imports_persistence(self):
        # Required by the resume path on /start.
        src = inspect.getsource(rh_mod)
        assert "import runtime_persistence" in src

    def test_persistence_does_not_import_session_loop(self):
        # Persistence is the leaf; it must not depend on layers above.
        src = inspect.getsource(rp_mod)
        for forbidden in (
            "from session_loop", "import session_loop",
            "from runtime_http", "import runtime_http",
            "from operator_session_runner",
        ):
            assert forbidden not in src
