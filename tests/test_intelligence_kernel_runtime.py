"""
PASS-5 Phase D — intelligence_kernel runtime tests.

Concurrency + multi-instance determinism across BD2 (kernel).

Covers:
    D4 — Macro run-id determinism under concurrency
         (50 concurrent macro invocations must produce 50 distinct
         ``macro_<ts_ms>_<seq>`` ids; ``_macro_seq_lock`` must
         prevent duplicates.)
"""
from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import intelligence_kernel as ik


_MACRO_ID_RE = re.compile(r"^macro_(\d+)_(\d+)$")


# ===========================================================================
# D4 — Macro run-id determinism under concurrency
# ===========================================================================
class TestD4MacroRunIdUnderConcurrency:
    """PASS-4 B2 pre-allocated ``_macro_seq_lock`` at module import,
    closing the lazy-init TOCTOU window. Under 50 concurrent macro
    invocations the lock must serialise the counter so every run_id
    is unique and matches the documented format
    ``macro_<ts_ms>_<seq>``."""

    def test_d4_fifty_concurrent_macro_invocations_produce_unique_ids(
        self, reset_stores, monkeypatch,
    ):
        N = 50
        captured: list[str] = []
        captured_lock = threading.Lock()

        # Capture every ``_make_macro_run_id`` result via a wrapper that
        # still delegates to the original — preserves real behaviour
        # while giving the test a hook to record every id allocated
        # under contention.
        original_make = ik._make_macro_run_id

        def capturing_make(now, seq=None):
            run_id = original_make(now, seq=seq)
            with captured_lock:
                captured.append(run_id)
            return run_id

        monkeypatch.setattr(ik, "_make_macro_run_id", capturing_make)

        # Each thread triggers a real macro run. The run path:
        #   _next_macro_seq() under _macro_seq_lock
        #   _make_macro_run_id(now, seq=seq)
        # is the exact code the B2 fix protects.
        barrier = threading.Barrier(parties=N)
        results: list[dict] = []
        results_lock = threading.Lock()

        def worker(idx: int) -> None:
            barrier.wait(timeout=15.0)
            summary = ik.run_macro_ELINS(f"scheduler_d4_{idx}")
            with results_lock:
                results.append(summary)

        with ThreadPoolExecutor(max_workers=N) as ex:
            futs = [ex.submit(worker, i) for i in range(N)]
            for f in futs:
                f.result(timeout=120.0)

        # Every macro run returned a summary with a run_id.
        assert len(results) == N
        returned_ids = [r["run_id"] for r in results]

        # No duplicates across the returned ids OR the captured ids.
        assert len(set(returned_ids)) == N, (
            f"duplicate run_ids in macro returns: "
            f"{len(returned_ids) - len(set(returned_ids))} collisions"
        )
        # _make_macro_run_id may be called once per macro run; the
        # capture list may have extras if the kernel calls the helper
        # in any auxiliary path, but the union must include every
        # returned id and remain duplicate-free.
        assert set(returned_ids).issubset(set(captured))
        assert len(set(captured)) == len(captured), (
            "_make_macro_run_id emitted duplicate ids — _macro_seq_lock "
            "did not serialise the counter"
        )

    def test_d4_run_id_format_under_concurrency(self, reset_stores):
        """Every id produced under load matches
        ``macro_<ts_ms>_<seq>`` — both halves are integers, the
        sequence is monotone, and the format is byte-stable with the
        single-thread ``_make_macro_run_id`` contract."""
        N = 50
        run_ids: list[str] = []
        run_ids_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker(idx: int) -> None:
            barrier.wait(timeout=15.0)
            summary = ik.run_macro_ELINS(f"scheduler_d4_fmt_{idx}")
            with run_ids_lock:
                run_ids.append(summary["run_id"])

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=120.0)

        assert len(run_ids) == N
        seqs: list[int] = []
        for rid in run_ids:
            m = _MACRO_ID_RE.match(rid)
            assert m is not None, f"run_id {rid!r} does not match macro_<ts_ms>_<seq>"
            ts_ms_str, seq_str = m.group(1), m.group(2)
            # Both halves parse as positive ints.
            assert int(ts_ms_str) > 0
            seqs.append(int(seq_str))

        # The seq values are exactly the integers the counter handed out
        # under load — set equality, no duplicates, no gaps relative to
        # the lowest one observed.
        assert len(set(seqs)) == N
        seqs_sorted = sorted(seqs)
        for i in range(len(seqs_sorted) - 1):
            assert seqs_sorted[i + 1] == seqs_sorted[i] + 1, (
                f"non-contiguous seq under load: {seqs_sorted}"
            )

    def test_d4_macro_seq_lock_remains_preallocated_after_load(
        self, reset_stores,
    ):
        """Defence-in-depth — after a concurrent macro burst the
        lock must still be the same pre-allocated ``threading.Lock``
        instance. Catches a regression where a stray code path
        re-introduced the lazy-init pattern."""
        lock_before = ik._macro_seq_lock
        N = 50
        barrier = threading.Barrier(parties=N)

        def worker(idx: int) -> None:
            barrier.wait(timeout=15.0)
            ik.run_macro_ELINS(f"scheduler_d4_lock_{idx}")

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=120.0)

        assert ik._macro_seq_lock is lock_before
        # And the lock is still usable.
        with ik._macro_seq_lock:
            pass
