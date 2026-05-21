"""
PASS-5 Phase D — memory_vault runtime tests.

Concurrency + determinism across BD5 (vault).

Covers:
    D5 — Key cache TTL under concurrency
         (PASS-4 FIX-H7 introduced (key_bytes, created_at) cache
         entries with a TTL. Under 50 concurrent ``_derive_key`` calls
         spanning a TTL boundary, every caller must receive the same
         deterministic PBKDF2 output, and the cache must end with a
         single coherent entry per user — no partial overwrites.)
"""
from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import memory_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _expected_key(user_id: str) -> bytes:
    """Compute the deterministic PBKDF2 key bytes for ``user_id`` with
    the same parameters the vault uses. Used as the ground-truth
    comparison value in every D5 test."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        memory_vault._secret(),
        ("clarityos:" + user_id).encode("utf-8"),
        memory_vault._pbkdf2_iters(),
        32,
    )


# ===========================================================================
# D5 — Key cache TTL under concurrency
# ===========================================================================
class TestD5KeyCacheTTLUnderConcurrency:
    def test_d5_concurrent_derive_after_cache_warm_returns_same_bytes(
        self, reset_stores,
    ):
        """Cache is warm and well within TTL — 50 concurrent
        ``_derive_key`` calls must all return the same cached bytes
        without re-running PBKDF2, and the cache entry's timestamp
        must NOT be bumped on read (no sliding window)."""
        # Pre-populate.
        first = memory_vault._derive_key("user_d5_warm")
        ts_after_seed = memory_vault._KEY_CACHE["user_d5_warm"][1]

        N = 50
        results: list[bytes] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker() -> None:
            barrier.wait(timeout=10.0)
            k = memory_vault._derive_key("user_d5_warm")
            with results_lock:
                results.append(k)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker) for _ in range(N)]:
                f.result(timeout=10.0)

        # Every thread saw the same bytes — the expected PBKDF2 output.
        assert len(results) == N
        assert all(k == first for k in results)
        assert first == _expected_key("user_d5_warm")

        # Cache has exactly one entry for this user, with the same
        # timestamp as immediately after the warm read (no read-time
        # bump under concurrency).
        entry = memory_vault._KEY_CACHE["user_d5_warm"]
        assert entry[0] == first
        assert entry[1] == ts_after_seed

    def test_d5_concurrent_derive_across_ttl_boundary_returns_same_bytes(
        self, reset_stores,
    ):
        """Cache entry is exactly past its TTL — 50 concurrent
        ``_derive_key`` calls race on the re-derivation path. Because
        PBKDF2 is deterministic, every caller must observe the same
        bytes. The cache ends with one entry whose timestamp is
        within the test's wall-clock window (last writer wins, but
        any winner is correct because the bytes are identical)."""
        user_id = "user_d5_boundary"
        expected = _expected_key(user_id)

        # Pre-populate, then push the timestamp 1s past the TTL so the
        # cache hit path falls through to the slow path on the first
        # call from every thread.
        memory_vault._derive_key(user_id)
        stale_ts = time.time() - memory_vault._KEY_CACHE_TTL_SECONDS - 1.0
        # Use the existing bytes — the test is about TTL handling, not
        # corruption detection.
        cached_bytes = memory_vault._KEY_CACHE[user_id][0]
        memory_vault._KEY_CACHE[user_id] = (cached_bytes, stale_ts)

        N = 50
        results: list[bytes] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)
        started_at = time.time()

        def worker() -> None:
            barrier.wait(timeout=15.0)
            k = memory_vault._derive_key(user_id)
            with results_lock:
                results.append(k)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker) for _ in range(N)]:
                f.result(timeout=30.0)
        finished_at = time.time()

        # Every thread observed the deterministic PBKDF2 output.
        assert len(results) == N
        assert all(k == expected for k in results), (
            "PBKDF2 output diverged across threads — this would mean the "
            "derivation parameters were perturbed by FIX-H7"
        )

        # Cache has a single, coherent entry — never two — for this user.
        new_entry = memory_vault._KEY_CACHE[user_id]
        new_bytes, new_ts = new_entry
        assert new_bytes == expected
        # Timestamp is from one of the writers during the test window.
        # (Last-write-wins under benign contention — any winner is fine
        # because all winners write the same bytes.)
        assert new_ts > stale_ts
        assert started_at <= new_ts <= finished_at + 0.5

    def test_d5_concurrent_derive_for_distinct_users_no_cross_contamination(
        self, reset_stores,
    ):
        """50 threads derive keys for 50 distinct users in parallel —
        each user gets the deterministic PBKDF2 output for its own
        id, never another user's bytes. Validates the per-user
        partitioning of ``_KEY_CACHE`` under concurrent first-derive
        contention."""
        N = 50
        user_ids = [f"user_d5_distinct_{i:03d}" for i in range(N)]
        expected = {u: _expected_key(u) for u in user_ids}
        observed: dict[str, bytes] = {}
        observed_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker(u: str) -> None:
            barrier.wait(timeout=15.0)
            k = memory_vault._derive_key(u)
            with observed_lock:
                observed[u] = k

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, u) for u in user_ids]:
                f.result(timeout=30.0)

        # Each user got the right bytes — no cross-contamination.
        assert observed == expected
        # And the cache has an entry for every user we touched.
        for u in user_ids:
            assert u in memory_vault._KEY_CACHE
            assert memory_vault._KEY_CACHE[u][0] == expected[u]

    def test_d5_invalidation_during_concurrent_reads_is_safe(
        self, reset_stores,
    ):
        """One thread invalidates while others are deriving — every
        caller still receives a valid key (either the cached value
        before invalidation, or a freshly-derived one after). No
        thread sees corrupted bytes, no AttributeError, no KeyError."""
        user_id = "user_d5_invalidate_race"
        expected = _expected_key(user_id)

        # Pre-populate.
        memory_vault._derive_key(user_id)

        N = 50
        results: list[bytes] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N + 1)

        def reader() -> None:
            barrier.wait(timeout=15.0)
            k = memory_vault._derive_key(user_id)
            with results_lock:
                results.append(k)

        def invalidator() -> None:
            barrier.wait(timeout=15.0)
            # Multiple invalidations during the burst, simulating a
            # secret-rotation event that fires mid-load.
            for _ in range(10):
                memory_vault._invalidate_key_cache_for_user(user_id)

        with ThreadPoolExecutor(max_workers=N + 1) as ex:
            futs = [ex.submit(reader) for _ in range(N)]
            futs.append(ex.submit(invalidator))
            for f in futs:
                f.result(timeout=30.0)

        # Every reader got the deterministic PBKDF2 bytes — invalidation
        # forced re-derivation but the result is identical.
        assert len(results) == N
        assert all(k == expected for k in results)

        # The cache ends in one of two valid states: present with the
        # right bytes, OR absent (the invalidator's last call fell
        # after every reader). Both are correct.
        entry = memory_vault._KEY_CACHE.get(user_id)
        if entry is not None:
            assert entry[0] == expected


# ===========================================================================
# PASS-6 Phase B — B5: Vault Behavior Under Deployment
# ===========================================================================
def _simulate_instance_reset_vault_caches_only() -> None:
    """Wipe only the per-process vault caches (key cache + plaintext
    one-shot flag). The persistence backend (``_MEM_STORE``, fs files,
    sqlite db) is left intact so writes from a previous "instance" are
    visible to the next."""
    memory_vault._KEY_CACHE.clear()
    memory_vault._PLAINTEXT_WARNING_EMITTED = False


class TestB5VaultUnderDeployment:
    """Deployment-shaped vault behaviour: encrypted round-trip under a
    production env config, TTL behaviour across simulated hours, no
    cross-instance contamination of the key cache, and namespace
    allow-list enforcement on the write path."""

    def test_b5_encrypted_round_trip_under_deployment_env(
        self, reset_stores, monkeypatch,
    ):
        """Default deployment config = encrypted mode with the secret
        from the env. A vault write followed by a read returns the
        same value."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        memory_vault._reset_for_tests()

        payload = {"thread_meta": "production-shape", "ts": 1.0}
        memory_vault.vault_put("b5_deploy_user", "threads.meta.t1", payload)
        got = memory_vault.vault_get("b5_deploy_user", "threads.meta.t1")
        assert got == payload
        # Confirm encryption is actually on (envelope scheme byte 0x01).
        import base64
        raw = base64.b64decode(
            memory_vault._encrypt_value(
                "b5_deploy_user", b"x",
            ).encode("ascii"),
        )
        assert raw[0] == 0x01

    def test_b5_key_cache_ttl_across_simulated_hours(self, reset_stores):
        """Walk the cache entry's timestamp backwards by hours to
        simulate a long-running container; verify the TTL re-derive
        path kicks in exactly at the documented boundary."""
        ttl = memory_vault._KEY_CACHE_TTL_SECONDS

        # Warm the cache.
        first = memory_vault._derive_key("b5_ttl_user")
        # Simulate "30 minutes elapsed" — well inside TTL.
        memory_vault._KEY_CACHE["b5_ttl_user"] = (
            first, memory_vault._KEY_CACHE["b5_ttl_user"][1] - (ttl / 2),
        )
        ts_before_call = memory_vault._KEY_CACHE["b5_ttl_user"][1]
        same = memory_vault._derive_key("b5_ttl_user")
        # Cache hit — no timestamp bump.
        assert same == first
        assert memory_vault._KEY_CACHE["b5_ttl_user"][1] == ts_before_call

        # Simulate "1 hour and 1 second elapsed" — past TTL.
        memory_vault._KEY_CACHE["b5_ttl_user"] = (
            first, memory_vault._KEY_CACHE["b5_ttl_user"][1] - (ttl + 1.0),
        )
        rederived = memory_vault._derive_key("b5_ttl_user")
        # Same bytes (deterministic PBKDF2), new timestamp.
        assert rederived == first
        new_ts = memory_vault._KEY_CACHE["b5_ttl_user"][1]
        assert new_ts > ts_before_call - (ttl + 1.0)

    def test_b5_no_cross_instance_contamination_of_key_cache(
        self, reset_stores,
    ):
        """Instance A populates the key cache; the simulated restart
        clears the cache (preserving the vault data) before instance
        B starts. Instance B must see an empty cache and re-derive
        the same key from scratch — proving no instance-local cache
        state leaks across the boundary."""
        # Instance A: warm the cache for two users.
        memory_vault._derive_key("b5_xinst_alice")
        memory_vault._derive_key("b5_xinst_bob")
        assert "b5_xinst_alice" in memory_vault._KEY_CACHE
        assert "b5_xinst_bob" in memory_vault._KEY_CACHE

        # Simulate restart — vault data preserved, caches cleared.
        _simulate_instance_reset_vault_caches_only()
        assert memory_vault._KEY_CACHE == {}

        # Instance B: re-derive — same deterministic bytes, fresh cache
        # entries (instance-local state is independent).
        alice_again = memory_vault._derive_key("b5_xinst_alice")
        bob_again = memory_vault._derive_key("b5_xinst_bob")
        # Bytes are deterministic; instance A's bytes and instance B's
        # bytes match because PBKDF2 inputs (secret + user_id) are the
        # same — that's the cross-instance invariant.
        import hashlib
        expected_alice = hashlib.pbkdf2_hmac(
            "sha256", memory_vault._secret(),
            b"clarityos:b5_xinst_alice",
            memory_vault._pbkdf2_iters(), 32,
        )
        assert alice_again == expected_alice

    def test_b5_namespace_allow_list_enforced_on_write(self, reset_stores):
        """Deployment guarantee — even when a vault is healthy and
        configured, an unknown namespace cannot land. The allow-list
        is the authority."""
        # Every known namespace accepts a sub-key.
        for ns in (
            "operator_state", "elins", "g_runs", "preferences",
            "local_model", "notes", "embeddings", "threads",
            "projects", "regression_chains", "regression_packets",
            "founder_global",
        ):
            memory_vault.vault_put("b5_ns_user", f"{ns}.sub_key", "v")
        # An unknown namespace is rejected at write time.
        for bad in ("admin", "secrets", "raw_log", "random_ns"):
            with pytest.raises(ValueError):
                memory_vault.vault_put(
                    "b5_ns_user", f"{bad}.sub_key", "v",
                )

    def test_b5_namespace_allow_list_enforced_on_read(self, reset_stores):
        """A read with an unknown namespace must also fail — the
        validator runs on every put/get/delete entry point."""
        with pytest.raises(ValueError):
            memory_vault.vault_get("b5_ns_user", "admin.sub_key")
        with pytest.raises(ValueError):
            memory_vault.vault_delete("b5_ns_user", "admin.sub_key")
