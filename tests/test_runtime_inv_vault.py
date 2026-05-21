"""
PASS-6 Phase A — BD5 (vault) architectural invariants.

Each test asserts a single locked invariant directly. These are NOT
behavior tests — they fail loudly if the documented contract for
``memory_vault`` is violated, regardless of whether any downstream
caller still happens to work.

Locked invariants covered:
    INV-V1 — _KEY_CACHE entries are (key_bytes, created_at) tuples
             with TTL = _KEY_CACHE_TTL_SECONDS = 3600.0
    INV-V2 — _derive_key is deterministic for (secret, user_id) under
             fixed PBKDF2 params (sha256, 100k iters, 32-byte output)
    INV-V3 — _invalidate_key_cache_for_user is idempotent + per-user
    INV-V4 — CLARITYOS_VAULT_PLAINTEXT only enables on explicit "true"
    INV-V5 — Plaintext warning fires exactly once per process
    INV-V6 — ALLOWED_NAMESPACES is the validation source of truth
    INV-V7 — Encrypt/decrypt round-trip is byte-stable; scheme bytes
             0x01 (encrypted) / 0x00 (plaintext) are preserved
    INV-V8 — _secret() raises RuntimeError when CLARITYOS_VAULT_SECRET
             is unset (no default-secret fallback in any environment)
"""
from __future__ import annotations

import base64
import hashlib
import logging

import pytest

import memory_vault


# ---------------------------------------------------------------------------
# INV-V1 — Cache entry shape + TTL constant
# ---------------------------------------------------------------------------
class TestINV_V1_KeyCacheShapeAndTTL:
    def test_inv_v1_ttl_constant_is_one_hour(self):
        """The PASS-4 FIX-H7 contract pins the cache TTL at 3600 seconds."""
        assert memory_vault._KEY_CACHE_TTL_SECONDS == 3600.0

    def test_inv_v1_cache_entries_are_two_tuples(self, reset_stores):
        memory_vault._derive_key("inv_v1_user")
        entry = memory_vault._KEY_CACHE["inv_v1_user"]
        assert isinstance(entry, tuple), (
            "INV-V1 violated — _KEY_CACHE entry is not a tuple"
        )
        assert len(entry) == 2, (
            "INV-V1 violated — _KEY_CACHE entry is not a 2-tuple"
        )
        key_bytes, created_at = entry
        assert isinstance(key_bytes, bytes) and len(key_bytes) == 32
        assert isinstance(created_at, float)


# ---------------------------------------------------------------------------
# INV-V2 — Determinism of _derive_key under fixed PBKDF2 params
# ---------------------------------------------------------------------------
class TestINV_V2_DeriveKeyDeterminism:
    def test_inv_v2_pbkdf2_default_iters_pinned(self):
        """The default PBKDF2 iteration count is 100k. The vault env
        knob may override, but the documented default must not drift."""
        assert memory_vault.DEFAULT_PBKDF2_ITERATIONS == 100_000

    def test_inv_v2_derive_key_matches_pbkdf2_formula(self, reset_stores):
        """``_derive_key`` must produce the byte-exact PBKDF2 output for
        the documented formula: PBKDF2-HMAC-SHA256(secret,
        b"clarityos:" + user_id, _pbkdf2_iters(), 32)."""
        user_id = "inv_v2_user"
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            memory_vault._secret(),
            ("clarityos:" + user_id).encode("utf-8"),
            memory_vault._pbkdf2_iters(),
            32,
        )
        got = memory_vault._derive_key(user_id)
        assert got == expected, "INV-V2 violated — PBKDF2 formula changed"

    def test_inv_v2_derive_key_returns_same_bytes_after_invalidation(
        self, reset_stores,
    ):
        """Re-derivation after explicit invalidation produces the same
        bytes — proves determinism is not coupled to cache state."""
        first = memory_vault._derive_key("inv_v2_redo")
        memory_vault._invalidate_key_cache_for_user("inv_v2_redo")
        second = memory_vault._derive_key("inv_v2_redo")
        assert first == second


# ---------------------------------------------------------------------------
# INV-V3 — Invalidation is idempotent + per-user
# ---------------------------------------------------------------------------
class TestINV_V3_InvalidationContract:
    def test_inv_v3_invalidate_unknown_user_is_noop(self, reset_stores):
        # Must not raise.
        memory_vault._invalidate_key_cache_for_user("inv_v3_never_existed")
        memory_vault._invalidate_key_cache_for_user("inv_v3_never_existed")

    def test_inv_v3_invalidate_only_targets_named_user(self, reset_stores):
        memory_vault._derive_key("inv_v3_alice")
        memory_vault._derive_key("inv_v3_bob")
        memory_vault._invalidate_key_cache_for_user("inv_v3_alice")
        assert "inv_v3_alice" not in memory_vault._KEY_CACHE
        assert "inv_v3_bob" in memory_vault._KEY_CACHE

    def test_inv_v3_invalidate_non_string_is_safe(self, reset_stores):
        # Defensive — the helper accepts any input without crashing.
        memory_vault._invalidate_key_cache_for_user(None)  # type: ignore[arg-type]
        memory_vault._invalidate_key_cache_for_user("")
        memory_vault._invalidate_key_cache_for_user(123)   # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# INV-V4 — CLARITYOS_VAULT_PLAINTEXT only enables on explicit "true"
# ---------------------------------------------------------------------------
class TestINV_V4_PlaintextEnablement:
    @pytest.mark.parametrize("legacy", ["1", "yes", "on", "y", "ok", "True!"])
    def test_inv_v4_loose_values_no_longer_enable(
        self, reset_stores, monkeypatch, legacy,
    ):
        """Anything other than the literal ``"true"`` (case-insensitive
        + whitespace-trimmed) MUST leave encryption ON."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", legacy)
        assert memory_vault._is_encrypted() is True, (
            f"INV-V4 violated — value {legacy!r} unexpectedly enabled plaintext"
        )

    @pytest.mark.parametrize("explicit", ["true", "True", "TRUE", "  true  "])
    def test_inv_v4_explicit_true_enables(
        self, reset_stores, monkeypatch, explicit,
    ):
        memory_vault._reset_for_tests()  # clear the one-shot warn flag
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", explicit)
        assert memory_vault._is_encrypted() is False


# ---------------------------------------------------------------------------
# INV-V5 — Plaintext warning fires exactly once per process
# ---------------------------------------------------------------------------
class TestINV_V5_PlaintextOneShotWarning:
    def test_inv_v5_warning_fires_exactly_once(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        # Many calls — only the first must emit.
        for _ in range(25):
            memory_vault._is_encrypted()

        warnings = [
            rec for rec in caplog.records
            if rec.name == "clarityos.memory_vault"
            and rec.levelno == logging.WARNING
            and "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(warnings) == 1, (
            f"INV-V5 violated — expected exactly one PLAINTEXT warning, "
            f"got {len(warnings)}"
        )


# ---------------------------------------------------------------------------
# INV-V6 — Namespace allow-list is the validation source of truth
# ---------------------------------------------------------------------------
class TestINV_V6_NamespaceAllowList:
    # The frozen registry the runtime depends on. Adding a namespace
    # must be a deliberate, reviewable change — this test gates that
    # by forcing every addition to also update the expected set here.
    _EXPECTED_NAMESPACES: frozenset[str] = frozenset({
        "operator_state",
        "elins",
        "g_runs",
        "preferences",
        "local_model",
        "notes",
        "embeddings",
        "threads",
        "projects",
        "regression_chains",
        "regression_packets",
        "founder_global",
    })

    def test_inv_v6_allowed_namespaces_matches_frozen_registry(self):
        assert frozenset(memory_vault.ALLOWED_NAMESPACES) == self._EXPECTED_NAMESPACES, (
            "INV-V6 violated — ALLOWED_NAMESPACES drift. If you added or "
            "removed a namespace, update _EXPECTED_NAMESPACES in this test "
            "after architectural review."
        )

    def test_inv_v6_unknown_namespace_rejected_by_validator(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault._validate_key("nope.some_key")

    def test_inv_v6_namespace_without_subkey_rejected(self, reset_stores):
        for ns in self._EXPECTED_NAMESPACES:
            with pytest.raises(ValueError):
                memory_vault._validate_key(ns)
            with pytest.raises(ValueError):
                memory_vault._validate_key(ns + ".")

    def test_inv_v6_key_with_slash_or_null_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault._validate_key("notes.a/b")
        with pytest.raises(ValueError):
            memory_vault._validate_key("notes.a\x00b")


# ---------------------------------------------------------------------------
# INV-V7 — Encrypt/decrypt round-trip is byte-stable, scheme bytes preserved
# ---------------------------------------------------------------------------
class TestINV_V7_RoundTripContract:
    def test_inv_v7_round_trip_encrypted_mode(self, reset_stores, monkeypatch):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        memory_vault._reset_for_tests()

        envelope = memory_vault._encrypt_value("inv_v7_user", b"the quick brown fox")
        # Scheme byte is 0x01 (HMAC-CTR + MAC).
        raw = base64.b64decode(envelope.encode("ascii"))
        assert raw[0] == 0x01

        plaintext = memory_vault._decrypt_value("inv_v7_user", envelope)
        assert plaintext == b"the quick brown fox"

    def test_inv_v7_round_trip_plaintext_mode(self, reset_stores, monkeypatch):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        memory_vault._reset_for_tests()

        envelope = memory_vault._encrypt_value("inv_v7_pt", b"bytes-in-the-clear")
        raw = base64.b64decode(envelope.encode("ascii"))
        # Scheme byte 0x00 (plaintext, no MAC) — visible in the envelope.
        assert raw[0] == 0x00

        plaintext = memory_vault._decrypt_value("inv_v7_pt", envelope)
        assert plaintext == b"bytes-in-the-clear"

    def test_inv_v7_mac_mismatch_raises(self, reset_stores, monkeypatch):
        """Tampering with the ciphertext must fail the MAC check; the
        decryptor raises rather than returning garbage."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        memory_vault._reset_for_tests()

        envelope = memory_vault._encrypt_value("inv_v7_mac", b"original")
        raw = bytearray(base64.b64decode(envelope.encode("ascii")))
        # Flip one ciphertext byte (after scheme + 16-byte nonce, before
        # the 32-byte MAC tail).
        target_idx = 1 + 16
        raw[target_idx] ^= 0x01
        tampered = base64.b64encode(bytes(raw)).decode("ascii")

        with pytest.raises(ValueError):
            memory_vault._decrypt_value("inv_v7_mac", tampered)


# ---------------------------------------------------------------------------
# INV-V8 — _secret() raises on missing CLARITYOS_VAULT_SECRET
# ---------------------------------------------------------------------------
class TestINV_V8_SecretRequired:
    def test_inv_v8_unset_secret_raises_runtime_error(
        self, reset_stores, monkeypatch,
    ):
        """No default-secret fallback in ANY environment — a missing
        secret is a hard error so a misconfigured deployment fails
        loudly instead of silently encrypting under a known key."""
        monkeypatch.delenv("CLARITYOS_VAULT_SECRET", raising=False)
        with pytest.raises(RuntimeError) as ei:
            memory_vault._secret()
        # Message must explicitly name the env var so the operator can
        # diagnose the failure without reading source.
        assert "CLARITYOS_VAULT_SECRET" in str(ei.value)

    def test_inv_v8_empty_secret_raises_runtime_error(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "")
        with pytest.raises(RuntimeError):
            memory_vault._secret()

    def test_inv_v8_whitespace_only_secret_raises_runtime_error(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "   ")
        with pytest.raises(RuntimeError):
            memory_vault._secret()
