"""
PASS-4 B2 — ``_macro_seq_lock`` is pre-allocated at import.

The pre-fix code held ``_macro_seq_lock = None`` until the first call
to ``_next_macro_seq`` and lazily installed a Lock under a TOCTOU
window:

    if _macro_seq_lock is None:
        _macro_seq_lock = threading.Lock()
    with _macro_seq_lock:
        _macro_seq += 1
        return _macro_seq

Two concurrent threads / tasks could both observe ``None`` and each
install a fresh Lock, with only one of those Locks actually being kept
in the module global. The thread holding the dropped Lock would then
serialise against itself only, while the other thread serialised
against the kept Lock — meaning the ``_macro_seq += 1`` step could
race, producing duplicate or out-of-order sequence values.

The fix pre-allocates the Lock at module import so every caller
observes the same Lock instance from the very first call onwards.

Tests:
    A. Single-thread sequencing — strictly +1, no gaps, no duplicates.
    B. Concurrent threads — N invocations produce exactly {1..N} with
       no duplicates or out-of-order skips.
    C. Pre-allocation guarantee — ``_macro_seq_lock`` is a Lock
       immediately after a fresh import (no lazy init required).
    D. Reset preserves the lock instance — ``_reset_for_tests`` only
       zeroes the counter, never nulls the lock.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import intelligence_kernel as ik


# ---------------------------------------------------------------------------
# Test A — Single-thread sequencing
# ---------------------------------------------------------------------------
def test_single_thread_sequence_is_strictly_increasing(reset_stores):
    """Sequential calls return 1, 2, 3, ... with no gaps or
    duplicates. This is the baseline contract; the rest of the suite
    builds on it."""
    seen = [ik._next_macro_seq() for _ in range(20)]
    assert seen == list(range(1, 21))


def test_single_thread_no_duplicates_no_gaps(reset_stores):
    """A second batch immediately after the first must continue the
    sequence — no reset, no replays."""
    first = [ik._next_macro_seq() for _ in range(5)]
    second = [ik._next_macro_seq() for _ in range(5)]
    assert first == [1, 2, 3, 4, 5]
    assert second == [6, 7, 8, 9, 10]
    assert len(set(first + second)) == 10


# ---------------------------------------------------------------------------
# Test B — Concurrency safety
# ---------------------------------------------------------------------------
def test_concurrent_threads_produce_unique_consecutive_sequence(reset_stores):
    """N threads each call ``_next_macro_seq`` once. The union of
    observed values must equal ``{1..N}`` exactly — no duplicates from
    a race, no skips from a Lock that didn't actually serialise."""
    N = 200
    results: list[int] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(parties=N)

    def worker():
        # All threads release together so the contention is maximal
        # and the previously-racy lazy-init window (if it existed)
        # would be reliably triggered.
        barrier.wait(timeout=10.0)
        seq = ik._next_macro_seq()
        with results_lock:
            results.append(seq)

    with ThreadPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(worker) for _ in range(N)]
        for f in futs:
            f.result(timeout=10.0)

    assert len(results) == N
    assert sorted(results) == list(range(1, N + 1))
    assert len(set(results)) == N


def test_concurrent_threads_with_large_batch_per_thread(reset_stores):
    """Each thread pulls a batch of M ids. After all threads finish,
    the multiset of ids must equal ``{1..T*M}`` — i.e. every id
    appears exactly once and the counter never lost an increment."""
    T = 16        # threads
    M = 50        # ids per thread
    results: list[int] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(parties=T)

    def worker():
        barrier.wait(timeout=10.0)
        local = [ik._next_macro_seq() for _ in range(M)]
        with results_lock:
            results.extend(local)

    with ThreadPoolExecutor(max_workers=T) as ex:
        futs = [ex.submit(worker) for _ in range(T)]
        for f in futs:
            f.result(timeout=10.0)

    assert len(results) == T * M
    assert sorted(results) == list(range(1, T * M + 1))


# ---------------------------------------------------------------------------
# Test C — Pre-allocation guarantee (the actual B2 mitigation surface)
# ---------------------------------------------------------------------------
def test_macro_seq_lock_is_preallocated_after_import(reset_stores):
    """The lock must be a usable ``threading.Lock`` immediately after a
    fresh reset — no first-call required to install it. This is what
    closes the TOCTOU race."""
    # Sanity: the attribute exists and is a Lock.
    assert ik._macro_seq_lock is not None
    # A Lock instance exposes acquire / release / __enter__ / __exit__.
    assert hasattr(ik._macro_seq_lock, "acquire")
    assert hasattr(ik._macro_seq_lock, "release")
    # And it is actually usable as a context manager.
    with ik._macro_seq_lock:
        pass


def test_macro_seq_lock_identity_stable_across_reset(reset_stores):
    """``_reset_for_tests`` must NOT null the lock — doing so would
    re-introduce the original TOCTOU window between tests. Confirm the
    same Lock instance survives a reset."""
    lock_before = ik._macro_seq_lock
    ik._next_macro_seq()
    ik._next_macro_seq()
    ik._reset_for_tests()
    lock_after = ik._macro_seq_lock
    assert lock_after is lock_before


def test_reset_zeroes_counter_only(reset_stores):
    """``_reset_for_tests`` zeroes ``_macro_seq`` but leaves the lock
    pre-allocated. The next ``_next_macro_seq`` therefore returns 1
    again — same as a fresh process."""
    _ = [ik._next_macro_seq() for _ in range(5)]
    ik._reset_for_tests()
    assert ik._macro_seq == 0
    assert ik._next_macro_seq() == 1


# ---------------------------------------------------------------------------
# Test D — Macro run-id format unchanged
# ---------------------------------------------------------------------------
def test_macro_run_id_format_unchanged(reset_stores):
    """The B2 mitigation must not change the macro_run_id format. The
    id is ``macro_{ts_ms}_{seq}`` and the seq is the int returned by
    ``_next_macro_seq``; both halves stay shaped exactly as before."""
    now = 1_700_000_000.0
    rid = ik._make_macro_run_id(now, seq=ik._next_macro_seq())
    # int(now * 1000) = 1700000000000
    assert rid == "macro_1700000000000_1"
    rid2 = ik._make_macro_run_id(now, seq=ik._next_macro_seq())
    assert rid2 == "macro_1700000000000_2"
