"""
PASS-4 FIX-H7 — ``_KEY_CACHE`` has a TTL and explicit invalidation.

The pre-fix code held PBKDF2-derived keys in ``_KEY_CACHE`` for the
lifetime of the process — once a key was derived, it stayed in memory
until ``_reset_for_tests``. The fix:

  * stores each entry as ``(key_bytes, created_at_timestamp)``;
  * bounds reuse by ``_KEY_CACHE_TTL_SECONDS`` (default 3600s);
  * adds ``_invalidate_key_cache_for_user`` for explicit eviction.

Constraints that must NOT change (and these tests verify):
  * the on-the-wire encryption scheme (HMAC-CTR + HMAC-SHA256 MAC);
  * the PBKDF2 parameters (sha256, 100k iters, 32-byte output,
    salt ``"clarityos:" + user_id``);
  * the public API surface — callers continue to receive a valid key
    on every ``_derive_key`` call regardless of cache state.
"""
from __future__ import annotations

import hashlib
import os
import time

import pytest

import memory_vault as mv


# ---------------------------------------------------------------------------
# Module shape — the constants exist and are usable
# ---------------------------------------------------------------------------
class TestShape:
    def test_ttl_constant_exists_and_is_positive(self):
        assert isinstance(mv._KEY_CACHE_TTL_SECONDS, (int, float))
        assert mv._KEY_CACHE_TTL_SECONDS > 0

    def test_key_cache_entry_shape_is_tuple_after_derive(self, reset_stores):
        mv._derive_key("alice")
        entry = mv._KEY_CACHE.get("alice")
        assert entry is not None
        # (key_bytes, created_at) — two-tuple where item[0] is 32 bytes.
        assert isinstance(entry, tuple) and len(entry) == 2
        key_bytes, created_at = entry
        assert isinstance(key_bytes, bytes) and len(key_bytes) == 32
        assert isinstance(created_at, float)


# ---------------------------------------------------------------------------
# Test A — TTL expiry forces re-derivation
# ---------------------------------------------------------------------------
class TestTTLExpiry:
    def test_expired_entry_is_replaced_on_next_lookup(self, reset_stores):
        """Insert a cache entry with an artificially old ``created_at``
        (older than ``_KEY_CACHE_TTL_SECONDS``). The next
        ``_derive_key`` must re-derive and replace the entry; the
        returned key still matches the deterministic PBKDF2 output."""
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            mv._secret(),
            ("clarityos:" + "alice").encode("utf-8"),
            mv._pbkdf2_iters(),
            32,
        )

        # Seed the cache with an obviously-stale entry — a sentinel
        # bytes value plus a timestamp far in the past.
        stale_bytes = b"\xff" * 32
        stale_ts = time.time() - mv._KEY_CACHE_TTL_SECONDS - 60.0
        mv._KEY_CACHE["alice"] = (stale_bytes, stale_ts)

        derived = mv._derive_key("alice")
        # The returned key is the freshly-derived one, NOT the sentinel.
        assert derived == expected
        assert derived != stale_bytes

        # The cache entry has been replaced (new timestamp, real key).
        new_entry = mv._KEY_CACHE.get("alice")
        assert new_entry is not None
        new_key_bytes, new_created_at = new_entry
        assert new_key_bytes == expected
        assert new_created_at > stale_ts
        # The new timestamp is recent (within a few seconds of now).
        assert abs(new_created_at - time.time()) < 5.0

    def test_just_under_ttl_does_not_re_derive(self, reset_stores):
        """An entry whose age is just under the TTL stays in place —
        the cache hit path returns the cached bytes without running
        PBKDF2 again."""
        mv._derive_key("bob")
        entry = mv._KEY_CACHE["bob"]
        key_bytes_before, _ts_before = entry

        # Walk the timestamp back so the entry's age is TTL/2 — still
        # within the live window.
        mv._KEY_CACHE["bob"] = (
            key_bytes_before,
            time.time() - (mv._KEY_CACHE_TTL_SECONDS / 2.0),
        )
        ts_after_seed = mv._KEY_CACHE["bob"][1]

        derived = mv._derive_key("bob")
        assert derived == key_bytes_before
        # The timestamp was NOT touched — same value before and after
        # the lookup confirms the slow path didn't run.
        assert mv._KEY_CACHE["bob"][1] == ts_after_seed


# ---------------------------------------------------------------------------
# Test B — Fresh entries are reused within TTL
# ---------------------------------------------------------------------------
class TestFreshReuse:
    def test_repeat_lookup_within_ttl_returns_same_key(self, reset_stores):
        """Back-to-back lookups inside the TTL window return the same
        bytes — and the cache timestamp is NOT bumped on every read
        (no sliding-window behaviour)."""
        first = mv._derive_key("carol")
        ts_after_first = mv._KEY_CACHE["carol"][1]
        second = mv._derive_key("carol")
        ts_after_second = mv._KEY_CACHE["carol"][1]
        assert first == second
        assert ts_after_first == ts_after_second

    def test_different_users_get_different_cached_entries(self, reset_stores):
        """Per-user partitioning of the cache survives the FIX-H7
        change. ``alice`` and ``bob`` derive independently and each
        gets their own cache entry."""
        a = mv._derive_key("alice")
        b = mv._derive_key("bob")
        assert a != b
        assert mv._KEY_CACHE["alice"][0] == a
        assert mv._KEY_CACHE["bob"][0] == b


# ---------------------------------------------------------------------------
# Test C — Explicit invalidation
# ---------------------------------------------------------------------------
class TestInvalidation:
    def test_invalidation_forces_re_derivation(self, reset_stores):
        """After ``_invalidate_key_cache_for_user`` removes the entry,
        the very next ``_derive_key`` must re-run PBKDF2 and produce a
        fresh cache record. The returned key bytes are identical (same
        secret + salt + iters), but the cache timestamp advances."""
        mv._derive_key("dave")
        old_ts = mv._KEY_CACHE["dave"][1]

        mv._invalidate_key_cache_for_user("dave")
        assert "dave" not in mv._KEY_CACHE

        # Sleep just enough so the new created_at strictly exceeds the
        # old one even on a coarse clock. Keep the wait tiny — tests
        # must stay snappy.
        time.sleep(0.01)
        rederived = mv._derive_key("dave")
        new_entry = mv._KEY_CACHE["dave"]
        new_key_bytes, new_ts = new_entry

        assert rederived == new_key_bytes
        assert new_ts > old_ts

    def test_invalidation_is_idempotent(self, reset_stores):
        """Calling invalidation for a user with no cache entry is a
        no-op — never raises."""
        # User has no entry yet.
        mv._invalidate_key_cache_for_user("emma")
        # Still no entry.
        assert "emma" not in mv._KEY_CACHE
        # Second call also a no-op.
        mv._invalidate_key_cache_for_user("emma")
        assert "emma" not in mv._KEY_CACHE

    def test_invalidation_only_targets_named_user(self, reset_stores):
        """Invalidating ``alice`` must not evict other users' entries."""
        mv._derive_key("alice")
        mv._derive_key("bob")
        mv._invalidate_key_cache_for_user("alice")
        assert "alice" not in mv._KEY_CACHE
        assert "bob" in mv._KEY_CACHE


# ---------------------------------------------------------------------------
# Integration — encryption round-trip still works after TTL expiry
# ---------------------------------------------------------------------------
class TestEncryptionInvariants:
    def test_value_round_trips_through_ttl_boundary(self, reset_stores):
        """A value encrypted before the TTL expires must still be
        decryptable after the cache entry has been re-derived. The
        re-derived key is mathematically the same — only the cache
        timestamp moves — so this confirms PBKDF2 parameters were
        not perturbed by FIX-H7."""
        envelope = mv._encrypt_value("frank", b"payload-1234567890")

        # Age the cache entry past TTL.
        key_bytes, _ts = mv._KEY_CACHE["frank"]
        mv._KEY_CACHE["frank"] = (
            key_bytes,
            time.time() - mv._KEY_CACHE_TTL_SECONDS - 1.0,
        )

        # Decrypt through the same envelope; the re-derivation path
        # produces the same key, so the MAC verifies and the plaintext
        # comes back unchanged.
        plaintext = mv._decrypt_value("frank", envelope)
        assert plaintext == b"payload-1234567890"

    def test_pbkdf2_parameters_unchanged(self, reset_stores):
        """Hard-pin the PBKDF2 parameters — FIX-H7 must not silently
        re-tune iterations or output length."""
        # 100k iterations is the documented default; check the helper
        # still returns it when no override env is set.
        if "CLARITYOS_VAULT_PBKDF2" in os.environ:
            del os.environ["CLARITYOS_VAULT_PBKDF2"]
        assert mv._pbkdf2_iters() == mv.DEFAULT_PBKDF2_ITERATIONS == 100_000

        # 32-byte output, sha256 — derive twice and check the length.
        k = mv._derive_key("grace")
        assert len(k) == 32
