"""
Tests for v69 / Unit 74 — EL/INS per-turn hook in
``intelligence_kernel.run_thread_message``.

Covers:
    A. Default (flag off) → no records stored after a chat turn
    B. Flag on → one per_turn record stored per chat turn
    C. Hook failures do not break the chat response
    D. operator_state surfaces the flag through get_operator_state
"""
from __future__ import annotations

import time

import pytest

import el_ins
import intelligence_kernel as ik
import model_router as mr
import operator_state
import threads_vault


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    el_ins._reset_for_tests()
    # Stub the model router so run_thread_message never goes to network.
    monkeypatch.setattr(
        mr, "route_request",
        lambda model_id, prompt, **kw: {
            "ok": True, "text": "(mock reply)", "model_id": model_id,
            "provider": "mock", "mock": True, "ts": time.time(),
        },
    )
    yield
    el_ins._reset_for_tests()


# ===========================================================================
# A. Default off — no records
# ===========================================================================
class TestDefaultOff:
    def test_flag_defaults_to_false(self):
        state = operator_state.get_operator_state("alice")
        assert state["el_ins_per_turn"] is False

    def test_chat_turn_without_flag_does_not_store_el_ins(self):
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]
        ik.run_thread_message("alice", tid, "catastrophic doom")
        # No el_ins records.
        assert el_ins.get_recent_el_ins("alice") == []


# ===========================================================================
# B. Flag on — one per_turn record per chat turn
# ===========================================================================
class TestFlagOn:
    def test_chat_turn_with_flag_stores_per_turn_record(self):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]
        ik.run_thread_message("alice", tid, "catastrophic disaster doom panic")
        rows = el_ins.get_recent_el_ins("alice")
        assert len(rows) == 1
        rec = rows[0]
        assert rec["source"] == "per_turn"
        assert rec["thread_id"] == tid
        assert rec["operator_id"] == "alice"
        assert rec["result"]["analysis"]["ratio_classification"] == "high_el"

    def test_per_turn_record_uses_deterministic_mode(self):
        # The hook is meant to be cheap. Confirm by stubbing
        # _llm_analyze to raise — if the hook accidentally hit LLM mode,
        # the chat turn would still succeed (analyzer falls back) but
        # the LLM stub would be called. We assert it ISN'T.
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]
        called = {"n": 0}
        from el_ins import el_ins_analyzer as ea
        original = ea._llm_analyze

        def _spy(text):
            called["n"] += 1
            return original(text)

        try:
            ea._llm_analyze = _spy  # type: ignore[assignment]
            ik.run_thread_message("alice", tid, "statute clause testimony")
        finally:
            ea._llm_analyze = original  # type: ignore[assignment]
        assert called["n"] == 0, "per-turn hook should use deterministic mode"

    def test_multiple_turns_append_records(self):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]
        for msg in ["catastrophic", "statute", "everyday content"]:
            ik.run_thread_message("alice", tid, msg)
        rows = el_ins.get_recent_el_ins("alice")
        assert len(rows) == 3
        assert all(r["source"] == "per_turn" for r in rows)

    def test_turning_flag_back_off_stops_storage(self):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]
        ik.run_thread_message("alice", tid, "catastrophic")
        assert len(el_ins.get_recent_el_ins("alice")) == 1
        operator_state.set_el_ins_per_turn("alice", False)
        ik.run_thread_message("alice", tid, "statute clause")
        # No new record after flag flipped off.
        assert len(el_ins.get_recent_el_ins("alice")) == 1


# ===========================================================================
# C. Failure isolation — hook never breaks the chat response
# ===========================================================================
class TestFailureIsolation:
    def test_hook_failure_does_not_break_chat(self, monkeypatch):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="hello")["thread_id"]

        # Make the store raise. The chat turn must still succeed.
        def _boom(_record):
            raise RuntimeError("simulated store failure")

        monkeypatch.setattr(el_ins, "store_el_ins_record", _boom)
        result = ik.run_thread_message("alice", tid, "catastrophic")
        # Chat turn succeeded.
        assert result["assistant_message"]["content"] == "(mock reply)"


# ===========================================================================
# D. Operator-state surfaces the flag
# ===========================================================================
class TestOperatorStateExposure:
    def test_set_then_read_flag(self):
        operator_state.set_el_ins_per_turn("alice", True)
        assert operator_state.get_el_ins_per_turn("alice") is True
        operator_state.set_el_ins_per_turn("alice", False)
        assert operator_state.get_el_ins_per_turn("alice") is False

    def test_flag_persists_across_get_calls(self):
        operator_state.set_el_ins_per_turn("alice", True)
        state1 = operator_state.get_operator_state("alice")
        state2 = operator_state.get_operator_state("alice")
        assert state1["el_ins_per_turn"] is True
        assert state2["el_ins_per_turn"] is True
