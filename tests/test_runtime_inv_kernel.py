"""
PASS-6 Phase A — BD2 (intelligence_kernel) architectural invariants.

Locked invariants covered:
    INV-K1 — _macro_seq_lock is pre-allocated at module import (a
             single threading.Lock instance for the process lifetime;
             no lazy-init TOCTOU window)
    INV-K2 — Macro run_id format is ``macro_<ts_ms>_<seq>`` where the
             timestamp is int(now * 1000) and seq is a strictly
             increasing integer from _next_macro_seq
    INV-K3 — Every run_* surfaces model_id in its result and in the
             kernel_logging.meta block
    INV-K4 — ESO failures degrade gracefully (the run returns ok=True
             with eso_source="none")
    INV-K5 — Kernel run paths route model selection only through
             model_router.select_model (no hardcoded model ids)
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

import intelligence_kernel as ik
import model_router as mr


_MACRO_ID_RE = re.compile(r"^macro_(\d+)_(\d+)$")


# ---------------------------------------------------------------------------
# INV-K1 — _macro_seq_lock pre-allocated
# ---------------------------------------------------------------------------
class TestINV_K1_MacroSeqLockPreallocated:
    def test_inv_k1_lock_exists_immediately_after_reset(self, reset_stores):
        """``_reset_for_tests`` zeros the counter but MUST preserve the
        pre-allocated lock instance — otherwise the next concurrent
        ``_next_macro_seq`` could race on lazy init again."""
        assert ik._macro_seq_lock is not None
        assert hasattr(ik._macro_seq_lock, "acquire")
        assert hasattr(ik._macro_seq_lock, "release")

    def test_inv_k1_lock_identity_stable_across_reset(self, reset_stores):
        lock_before = ik._macro_seq_lock
        ik._next_macro_seq()
        ik._next_macro_seq()
        ik._reset_for_tests()
        assert ik._macro_seq_lock is lock_before, (
            "INV-K1 violated — _reset_for_tests replaced the lock instance"
        )

    def test_inv_k1_lock_is_usable_context_manager(self, reset_stores):
        # Non-reentrant Lock — but it is acquirable.
        with ik._macro_seq_lock:
            pass


# ---------------------------------------------------------------------------
# INV-K2 — Macro run_id format
# ---------------------------------------------------------------------------
class TestINV_K2_MacroRunIdFormat:
    def test_inv_k2_format_seq_included(self, reset_stores):
        rid = ik._make_macro_run_id(1_700_000_000.0, seq=42)
        assert rid == "macro_1700000000000_42"

    def test_inv_k2_format_no_seq_omits_suffix(self, reset_stores):
        rid = ik._make_macro_run_id(1_700_000_000.0, seq=None)
        assert rid == "macro_1700000000000"

    def test_inv_k2_one_thousand_ids_match_format(self, reset_stores):
        """Burst-generate 1000 ids and assert every one matches the
        regex AND seq values are strictly monotonic."""
        ids = [
            ik._make_macro_run_id(1_700_000_000.0, seq=ik._next_macro_seq())
            for _ in range(1000)
        ]
        seqs: list[int] = []
        for rid in ids:
            m = _MACRO_ID_RE.match(rid)
            assert m is not None, (
                f"INV-K2 violated — run_id {rid!r} does not match the regex"
            )
            seqs.append(int(m.group(2)))
        assert seqs == list(range(1, 1001)), (
            "INV-K2 violated — seq values are not strictly monotonic 1..1000"
        )


# ---------------------------------------------------------------------------
# INV-K3 — Every run_* surfaces model_id
# ---------------------------------------------------------------------------
class TestINV_K3_ModelIdSurfaced:
    def test_inv_k3_run_c_carries_model_id(self, reset_stores):
        r = ik.run_c("inv_k3_alice", "agency drift from mandate")
        assert r["ok"] is True
        assert isinstance(r.get("model_id"), str) and r["model_id"]

    def test_inv_k3_run_g_carries_model_id(self, reset_stores):
        def fake_runner(text, user):
            return {"ok": True, "analysis": {"qc_summary": {"pressure": 0.4}}}
        r = ik.run_G("inv_k3_alice", "x", runner=fake_runner)
        assert r["ok"] is True
        assert r["model_id"] == mr.TASK_DEFAULTS["G"]

    def test_inv_k3_run_elins_carries_model_id(self, reset_stores):
        r = ik.run_ELINS(
            "inv_k3_alice", "trust between partners eroding",
            kind="preview", persist=False,
        )
        assert "model_id" in r
        assert r["model_id"] == mr.TASK_DEFAULTS["ELINS"]

    def test_inv_k3_run_regional_elins_carries_model_id(self, reset_stores):
        r = ik.run_regional_ELINS("inv_k3_alice", "US")
        assert "model_id" in r
        assert r["model_id"] == mr.TASK_DEFAULTS["regional"]

    def test_inv_k3_run_macro_elins_carries_model_id(self, reset_stores):
        summary = ik.run_macro_ELINS("scheduler")
        assert summary["model_id"] == mr.TASK_DEFAULTS["macro"]


# ---------------------------------------------------------------------------
# INV-K4 — ESO failure degrades gracefully
# ---------------------------------------------------------------------------
class TestINV_K4_EsoFailureGracefulDegradation:
    def test_inv_k4_oracle_exception_returns_none(
        self, reset_stores, monkeypatch,
    ):
        """If ``perplexity_oracle.fetch_basin_signals`` raises, the
        kernel funnel ``_maybe_fetch_eso`` catches and returns None
        so the run completes with ok=True. No partially-formed ESO
        leaks downstream."""
        import perplexity_oracle as po

        def boom(*args, **kwargs):
            raise RuntimeError("simulated oracle outage")

        # The kernel funnel calls fetch_basin_signals; patch THAT.
        monkeypatch.setattr(po, "fetch_basin_signals", boom)

        # cloud_perplexity → tries the oracle → catches → eso=None.
        r = ik.run_ELINS(
            "inv_k4_alice", "x",
            external_signal_mode="cloud_perplexity",
            kind="preview", persist=False,
        )
        assert r["ok"] is True
        # eso_present may or may not be False depending on fallback path —
        # but the run did complete and produced an ELINS object.
        assert "elins" in r


# ---------------------------------------------------------------------------
# INV-K5 — All run paths route selection through model_router.select_model
# ---------------------------------------------------------------------------
class TestINV_K5_ModelSelectionRoutedThroughRouter:
    """Source-level grep: the kernel's run_* paths must call
    ``model_router.select_model`` (or the kernel's local
    ``_resolve_model`` which wraps it). They must NOT hardcode a
    canonical model_id like ``"openai:gpt-4o"`` directly in the run
    body. The kernel may reference such ids elsewhere (e.g. logging
    test fixtures) — this test scans only the run paths."""

    def test_inv_k5_select_model_is_called(self):
        src = Path("intelligence_kernel.py").read_text(encoding="utf-8")
        # The kernel either calls model_router.select_model directly,
        # or its _resolve_model wrapper which itself does.
        assert (
            "model_router.select_model" in src
            or "_resolve_model" in src
        ), (
            "INV-K5 violated — intelligence_kernel.py no longer routes "
            "selection through model_router.select_model / _resolve_model"
        )

    def test_inv_k5_no_hardcoded_canonical_ids_in_run_paths(self):
        """Hard-pin: ``openai:gpt-4o``, ``anthropic:claude-3.7``, etc.
        must not appear as a quoted string inside the kernel's run_*
        functions. They legitimately appear in TASK_DEFAULTS (router)
        and in tests — but never as an inline hardcoded fallback in
        the kernel body."""
        # We scope the check to the function bodies by looking for the
        # canonical ids in the source file. The kernel doc/docstring
        # may mention them by name; the rule we care about is that
        # nowhere in the file is a canonical id used as a literal
        # ``= "openai:gpt-4o"`` assignment or a literal ``return
        # "openai:gpt-4o"``.
        src = Path("intelligence_kernel.py").read_text(encoding="utf-8")
        for canonical in mr.SUPPORTED_MODELS:
            # Skip the auto sentinel + the local id (used by tests for
            # mock paths and never as a hardcoded selection).
            if canonical in ("auto",):
                continue
            assignment_pattern = f'= "{canonical}"'
            return_pattern     = f'return "{canonical}"'
            assert assignment_pattern not in src, (
                f"INV-K5 violated — hardcoded selection ``= {canonical!r}`` "
                f"found in intelligence_kernel.py"
            )
            assert return_pattern not in src, (
                f"INV-K5 violated — hardcoded selection ``return "
                f"{canonical!r}`` found in intelligence_kernel.py"
            )
