"""
Tests for v64 / Unit 64 — lost-update safe session step.

session_loop.step_session now reloads session + vault from
runtime_persistence at the top of every call before applying the
step. The caller's session_state is used only for identity.

Layered coverage:
    A. Scenario A — two sessions, same operator, interleaved steps
    B. Scenario B — step crashes mid-flow → no partial persisted state
    C. Stale-state caller — passing stale session_state still produces
       correct extension because reload happens server-side
    D. Cold start — load_session miss is tolerated (graceful fallback
       to caller's session_state for the very first step)
"""
from __future__ import annotations

import pytest

import model_router as mr
import operator_session_runner as osr_mod
import runtime_persistence as rp_mod
import session_loop as sl_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    clock_counter = {"n": 0}
    sid_counter   = {"n": 0}

    def fake_now():
        clock_counter["n"] += 1
        return f"2026-05-12T10:00:{clock_counter['n']:02d}+00:00"

    def fake_make_session_id():
        sid_counter["n"] += 1
        return f"sess-lu-{sid_counter['n']:03d}"

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)
    monkeypatch.delenv("CLARITYOS_RUNTIME_STORE_DIR", raising=False)
    rp_mod.reload_backend()
    rp_mod._reset_for_tests()
    mr._reset_for_tests()
    yield
    rp_mod._reset_for_tests()
    mr._reset_for_tests()


# ===========================================================================
# A. Scenario A — two sessions, same operator, interleaved steps
# ===========================================================================
class TestInterleavedSteps:
    def test_two_sessions_extend_shared_vault(self):
        # Both sessions belong to op_alice. Each step against either
        # session should reload the latest committed vault before
        # applying, so the final fusion_history reflects both
        # contributions.
        s1 = sl_mod.start_session("op_alice")
        s2 = sl_mod.start_session("op_alice")

        sl_mod.step_session(s1, "s1-step-1")
        # s2's vault_state is still empty (it was minted before
        # s1's step landed), but step_session reloads now so the
        # step sees s1's update.
        sl_mod.step_session(s2, "s2-step-1")
        sl_mod.step_session(s1, "s1-step-2")

        vault = rp_mod.load_vault("op_alice")
        # 3 contributions across two sessions, no lost updates.
        assert len(vault["elins"]["fusion_history"]) == 3

    def test_each_session_history_is_its_own(self):
        # Vault is shared across sessions for the operator, but each
        # session's history is its own (history is keyed by session,
        # not operator).
        s1 = sl_mod.start_session("op_alice")
        s2 = sl_mod.start_session("op_alice")
        r1 = sl_mod.step_session(s1, "s1-step-1")
        r2 = sl_mod.step_session(s2, "s2-step-1")

        assert len(r1["session_state"]["history"]) == 1
        assert r1["session_state"]["history"][0]["text"] == "s1-step-1"

        assert len(r2["session_state"]["history"]) == 1
        assert r2["session_state"]["history"][0]["text"] == "s2-step-1"

    def test_step_against_stale_returned_state(self):
        # Caller holds an old session_state object (pre-step). The
        # next step on that stale object should still reload the
        # latest persisted history before appending — so history
        # grows monotonically, not from a stale snapshot.
        s = sl_mod.start_session("op_alice")
        r1 = sl_mod.step_session(s, "step-1")

        # Note: we pass `s` (stale) NOT `r1["session_state"]`.
        r2 = sl_mod.step_session(s, "step-2")

        # r2's history should contain BOTH entries — step-2 reloaded
        # the persisted history from r1 before appending its own.
        history_texts = [e["text"] for e in r2["session_state"]["history"]]
        assert history_texts == ["step-1", "step-2"]


# ===========================================================================
# B. Scenario B — step crashes mid-flow → no partial state
# ===========================================================================
class TestCrashSafety:
    def test_crashed_step_leaves_persisted_state_unchanged(self, monkeypatch):
        # Set up: run one successful step so persistence has a known
        # baseline.
        s = sl_mod.start_session("op_alice")
        sl_mod.step_session(s, "baseline-step")

        before_vault = rp_mod.load_vault("op_alice")
        before_session = rp_mod.load_session(s["session_id"])
        assert before_vault is not None
        assert before_session is not None
        baseline_history_len = len(before_session["history"])
        baseline_vault_len = len(before_vault["elins"]["fusion_history"])

        # Simulate a crash inside the runtime step by monkey-patching
        # run_operator_session_step to raise.
        def boom(*_args, **_kwargs):
            raise RuntimeError("simulated runtime failure")

        monkeypatch.setattr(
            sl_mod, "run_operator_session_step", boom,
        )

        with pytest.raises(RuntimeError, match="simulated runtime failure"):
            sl_mod.step_session(s, "doomed-step")

        # Neither save should have run. Persisted state matches the
        # pre-crash snapshot.
        after_vault = rp_mod.load_vault("op_alice")
        after_session = rp_mod.load_session(s["session_id"])

        assert len(after_session["history"]) == baseline_history_len
        assert (
            len(after_vault["elins"]["fusion_history"])
            == baseline_vault_len
        )

    def test_crash_does_not_mutate_caller_session_state(self, monkeypatch):
        s = sl_mod.start_session("op_alice")
        import json
        snapshot = json.dumps(s, sort_keys=True)

        def boom(*_args, **_kwargs):
            raise RuntimeError("boom")
        monkeypatch.setattr(sl_mod, "run_operator_session_step", boom)

        with pytest.raises(RuntimeError):
            sl_mod.step_session(s, "doomed")

        assert json.dumps(s, sort_keys=True) == snapshot


# ===========================================================================
# C. Stale-state caller produces correct extension
# ===========================================================================
class TestStaleStateCallers:
    def test_three_steps_against_same_original_state(self):
        s = sl_mod.start_session("op_alice")
        # All three step calls pass the original `s` — under v43 this
        # would lose updates; under v64 each reloads first.
        sl_mod.step_session(s, "step-1")
        sl_mod.step_session(s, "step-2")
        sl_mod.step_session(s, "step-3")

        loaded = rp_mod.load_session(s["session_id"])
        texts = [e["text"] for e in loaded["history"]]
        assert texts == ["step-1", "step-2", "step-3"]

        vault = rp_mod.load_vault("op_alice")
        assert len(vault["elins"]["fusion_history"]) == 3


# ===========================================================================
# D. Cold-start tolerance — reload miss falls back to caller's state
# ===========================================================================
class TestColdStartTolerance:
    def test_first_step_works_even_if_session_not_persisted(self):
        # Build a session_state shape without going through
        # start_session — load_session will miss but the step
        # should still complete by falling back to the caller's
        # state.
        state = {
            "session_id":  "sess-bare-1",
            "operator_id": "op_alice",
            "vault_state": {},
            "history":     [],
        }
        # Confirm cold start: no prior persistence.
        assert rp_mod.load_session("sess-bare-1") is None
        assert rp_mod.load_vault("op_alice") is None

        out = sl_mod.step_session(state, "first-step")

        assert len(out["session_state"]["history"]) == 1
        assert (
            rp_mod.load_session("sess-bare-1")["history"][0]["text"]
            == "first-step"
        )
