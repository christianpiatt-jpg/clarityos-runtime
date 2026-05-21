"""
Tests for v62 / Unit 46 — per-operator save_vault lock.

The lock prevents partial-write corruption when two threads call
save_vault for the same operator concurrently. It does NOT solve
the v43 lost-update problem (each writer reads stale state and one
overwrites the other) — that's a session-loop concern, not a
persistence one. These tests verify the lock delivers what it
promises and nothing more.

Layered coverage (target ~12 tests):
    A. Lock registry plumbing
    B. Single-thread invariants preserved (no behaviour change)
    C. Concurrent in-memory writes — no partial state
    D. Concurrent file-mode writes — no temp-file corruption
    E. Per-operator scoping — different operators don't block each other
    F. Lock teardown via _reset_for_tests
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

import runtime_persistence as rp_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("CLARITYOS_RUNTIME_STORE_DIR", raising=False)
    rp_mod.reload_backend()
    rp_mod._reset_for_tests()
    yield
    rp_mod._reset_for_tests()
    monkeypatch.delenv("CLARITYOS_RUNTIME_STORE_DIR", raising=False)
    rp_mod.reload_backend()


@pytest.fixture
def file_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("CLARITYOS_RUNTIME_STORE_DIR", str(tmp_path))
    rp_mod.reload_backend()
    return tmp_path


def _vault(marker: int) -> dict:
    """Vault payload tagged with a marker so we can identify which
    writer's content is the final state on disk / in memory."""
    return {
        "elins": {
            "marker":         marker,
            "fusion_history": [{"step": i} for i in range(marker)],
            "last_fusion":    {"timestamp": f"2026-05-12T10:00:{marker:02d}+00:00"},
            "last_long_arc":  None,
        },
    }


# ===========================================================================
# A. Lock registry plumbing
# ===========================================================================
class TestLockRegistry:
    def test_lock_is_per_operator(self):
        a = rp_mod._operator_lock("op_alice")
        b = rp_mod._operator_lock("op_bob")
        assert a is not b

    def test_same_operator_returns_same_lock(self):
        a1 = rp_mod._operator_lock("op_alice")
        a2 = rp_mod._operator_lock("op_alice")
        assert a1 is a2

    def test_lock_registry_cleared_by_reset(self):
        rp_mod._operator_lock("op_alice")
        rp_mod._reset_for_tests()
        # After reset, a fresh lock object is minted.
        assert "op_alice" not in rp_mod._OPERATOR_LOCKS


# ===========================================================================
# B. Single-thread invariants preserved
# ===========================================================================
class TestSingleThreadInvariants:
    def test_save_then_load_unchanged(self):
        v = _vault(7)
        rp_mod.save_vault("op_alice", v)
        assert rp_mod.load_vault("op_alice") == v

    def test_overwrite_unchanged(self):
        rp_mod.save_vault("op_alice", _vault(1))
        rp_mod.save_vault("op_alice", _vault(2))
        assert rp_mod.load_vault("op_alice")["elins"]["marker"] == 2

    def test_validation_still_runs_before_lock(self):
        # Invalid operator_id must still raise — the lock acquisition
        # should never happen for malformed input.
        with pytest.raises(ValueError, match="operator_id"):
            rp_mod.save_vault("../etc/passwd", _vault(1))


# ===========================================================================
# C. Concurrent in-memory writes — no partial state
# ===========================================================================
class TestConcurrentInMemory:
    def test_two_writers_produce_a_complete_state(self):
        # Both threads write a complete vault payload. Whichever wins
        # the lock-race, the final state must be one writer's complete
        # payload — never an interleaved hybrid.
        barrier = threading.Barrier(2)

        def writer(marker: int):
            barrier.wait()
            rp_mod.save_vault("op_alice", _vault(marker))

        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(writer, 1), ex.submit(writer, 2)]
            for f in as_completed(futures):
                f.result()  # surfaces exceptions

        final = rp_mod.load_vault("op_alice")
        assert final is not None
        marker = final["elins"]["marker"]
        # Must be 1 OR 2 — never a mix or None.
        assert marker in (1, 2)
        # And the rest of the payload must match THAT marker (no
        # cross-writer interleaving inside the dict).
        assert len(final["elins"]["fusion_history"]) == marker

    def test_many_writers_no_exceptions(self):
        # 16 threads all writing to the same operator concurrently.
        # None should raise; final state must be a complete payload.
        N = 16
        barrier = threading.Barrier(N)
        errors: list[BaseException] = []

        def writer(marker: int):
            try:
                barrier.wait()
                rp_mod.save_vault("op_alice", _vault(marker))
            except BaseException as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in as_completed([
                ex.submit(writer, i) for i in range(N)
            ]):
                f.result()

        assert errors == []
        final = rp_mod.load_vault("op_alice")
        assert final is not None
        assert final["elins"]["marker"] in range(N)


# ===========================================================================
# D. Concurrent file-mode writes — no temp-file corruption
# ===========================================================================
class TestConcurrentFileMode:
    def test_file_contains_complete_json_after_concurrent_writes(
        self, file_backend,
    ):
        N = 8
        barrier = threading.Barrier(N)

        def writer(marker: int):
            barrier.wait()
            rp_mod.save_vault("op_alice", _vault(marker))

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in as_completed([
                ex.submit(writer, i + 1) for i in range(N)
            ]):
                f.result()

        # Read the file directly (NOT through load_vault, to be sure
        # we're checking what's actually on disk).
        path = file_backend / "vault" / "op_alice.json"
        raw = path.read_text(encoding="utf-8")
        # Must be parseable as JSON — no partial / truncated writes.
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        marker = parsed["elins"]["marker"]
        # And the marker must match what's in fusion_history (no
        # cross-writer interleaving).
        assert len(parsed["elins"]["fusion_history"]) == marker

    def test_no_stale_tmp_files_left(self, file_backend):
        # After concurrent writes, no .json.tmp files should remain
        # (each write replaces atomically before releasing the lock).
        N = 8
        barrier = threading.Barrier(N)

        def writer(marker: int):
            barrier.wait()
            rp_mod.save_vault("op_alice", _vault(marker))

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in as_completed([
                ex.submit(writer, i + 1) for i in range(N)
            ]):
                f.result()

        tmp_files = list((file_backend / "vault").glob("*.tmp"))
        assert tmp_files == []


# ===========================================================================
# E. Per-operator scoping — different operators don't block each other
# ===========================================================================
class TestPerOperatorScoping:
    def test_different_operators_do_not_serialize(self):
        # Hold Alice's lock manually. Bob's save must still complete
        # promptly — proving the lock is per-operator, not global.
        alice_lock = rp_mod._operator_lock("op_alice")
        held = threading.Event()
        release = threading.Event()

        def hog():
            with alice_lock:
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=hog, daemon=True)
        t.start()
        try:
            assert held.wait(timeout=2), "hog thread didn't acquire alice's lock"

            # Bob's save should not be blocked by alice's lock.
            t0 = time.perf_counter()
            rp_mod.save_vault("op_bob", _vault(99))
            elapsed = time.perf_counter() - t0
            # 0.5s is generous — without per-operator scoping this
            # would hang for the full hog-thread duration.
            assert elapsed < 0.5, (
                f"save_vault for op_bob blocked for {elapsed:.3f}s while "
                f"op_alice was held — lock is not per-operator"
            )
        finally:
            release.set()
            t.join(timeout=2)

    def test_isolated_writes_visible(self):
        rp_mod.save_vault("op_alice", _vault(1))
        rp_mod.save_vault("op_bob",   _vault(2))
        assert rp_mod.load_vault("op_alice")["elins"]["marker"] == 1
        assert rp_mod.load_vault("op_bob")["elins"]["marker"]   == 2


# ===========================================================================
# F. Lock teardown via _reset_for_tests
# ===========================================================================
class TestLockTeardown:
    def test_reset_clears_lock_registry(self):
        rp_mod._operator_lock("op_alice")
        rp_mod._operator_lock("op_bob")
        assert len(rp_mod._OPERATOR_LOCKS) == 2
        rp_mod._reset_for_tests()
        assert len(rp_mod._OPERATOR_LOCKS) == 0
