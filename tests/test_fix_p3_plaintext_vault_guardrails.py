"""
PASS-4 FIX-P3 — Explicit warning + guardrails for
``CLARITYOS_VAULT_PLAINTEXT``.

Two narrow changes to ``memory_vault._is_encrypted``:

  1. The enablement check is tightened from the loose
     ``raw not in ("1", "true", "yes")`` form to an explicit equality
     against ``"true"`` (case-insensitive). Anything else — including
     the previously-accepted ``"1"`` and ``"yes"`` — leaves encryption
     ON. This kills the accidental-enablement-by-typo path.

  2. The first time ``_is_encrypted`` observes plaintext mode in a
     given process, a high-severity warning is logged that names the
     env var, states encryption is disabled, and pins the warning to
     dev-only use. Subsequent calls are silent.

The encryption scheme, PBKDF2 parameters, and backend selection
remain untouched.
"""
from __future__ import annotations

import logging

import pytest

import memory_vault


# ---------------------------------------------------------------------------
# Test A — Explicit enablement (tightened parsing)
# ---------------------------------------------------------------------------
class TestExplicitEnablement:
    def test_unset_means_encryption_on(self, reset_stores, monkeypatch):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        assert memory_vault._is_encrypted() is True

    def test_explicit_true_disables_encryption(self, reset_stores, monkeypatch):
        """The one and only accepted enablement value."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        assert memory_vault._is_encrypted() is False

    def test_explicit_true_is_case_insensitive(self, reset_stores, monkeypatch):
        for spelling in ("TRUE", "True", "tRuE"):
            memory_vault._reset_for_tests()  # clear warning flag
            monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", spelling)
            assert memory_vault._is_encrypted() is False, (
                f"plaintext should be enabled for {spelling!r}"
            )

    def test_explicit_false_keeps_encryption_on(self, reset_stores, monkeypatch):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "false")
        assert memory_vault._is_encrypted() is True

    @pytest.mark.parametrize("legacy", ["1", "yes", "on", "y", "True!", "trueish"])
    def test_legacy_loose_values_no_longer_enable_plaintext(
        self, reset_stores, monkeypatch, legacy,
    ):
        """The pre-FIX-P3 check accepted ``"1"`` and ``"yes"`` (plus a
        few other truthy spellings via the docstring). After FIX-P3
        only the literal ``"true"`` enables plaintext mode — every
        other value, including legacy ones, leaves encryption ON.
        This is the documented tightening."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", legacy)
        assert memory_vault._is_encrypted() is True, (
            f"value {legacy!r} should no longer enable plaintext"
        )

    def test_empty_string_keeps_encryption_on(self, reset_stores, monkeypatch):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "")
        assert memory_vault._is_encrypted() is True

    def test_whitespace_only_keeps_encryption_on(self, reset_stores, monkeypatch):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "   ")
        assert memory_vault._is_encrypted() is True

    def test_whitespace_padded_true_still_enables(self, reset_stores, monkeypatch):
        """The implementation strips whitespace before comparing —
        ``"  true  "`` is the same as ``"true"`` from a caller's
        perspective. Matches the rest of the env-handling conventions
        in the module."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "  true  ")
        assert memory_vault._is_encrypted() is False


# ---------------------------------------------------------------------------
# Test B — Warning emitted exactly once per process
# ---------------------------------------------------------------------------
class TestOneTimeWarning:
    def test_warning_emitted_once_when_plaintext_enabled(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        # First observation → warning fires.
        memory_vault._is_encrypted()
        # Many subsequent observations → no additional warnings.
        for _ in range(10):
            memory_vault._is_encrypted()

        matching = [
            rec for rec in caplog.records
            if rec.name == "clarityos.memory_vault"
            and rec.levelno == logging.WARNING
            and "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(matching) == 1, (
            f"expected exactly one plaintext warning, got {len(matching)}"
        )

    def test_warning_message_names_env_var_and_dev_only(
        self, reset_stores, monkeypatch, caplog,
    ):
        """Sanity check on the warning content — the operator reading
        the log line should be able to identify (a) which env var
        triggered it and (b) that encryption is disabled / dev-only."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        memory_vault._is_encrypted()

        msgs = [rec.getMessage() for rec in caplog.records]
        joined = " | ".join(msgs)
        assert "CLARITYOS_VAULT_PLAINTEXT" in joined
        assert "encryption is" in joined.lower()
        assert "disabled" in joined.lower()
        # Hint at intended scope — dev / local only.
        assert "development" in joined.lower() or "local" in joined.lower()

    def test_no_warning_in_encrypted_mode(
        self, reset_stores, monkeypatch, caplog,
    ):
        """The warning must not fire when plaintext mode is off — that
        would create noise in every encrypted-mode deployment."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        for _ in range(5):
            memory_vault._is_encrypted()

        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT" in rec.getMessage().upper()
        ]
        assert plaintext_warnings == []


# ---------------------------------------------------------------------------
# Test C — No behavior change in encrypted mode
# ---------------------------------------------------------------------------
class TestEncryptedModeUnchanged:
    def test_encryption_round_trip_unchanged_when_var_unset(
        self, reset_stores, monkeypatch,
    ):
        """The default round-trip (encrypt → decrypt) is byte-for-byte
        unchanged when the env var is unset — FIX-P3 only adjusts the
        enablement parser, not the crypto path."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        assert memory_vault._is_encrypted() is True

        envelope = memory_vault._encrypt_value("alice", b"hello vault")
        # The envelope is encrypted (scheme byte 0x01 — not 0x00).
        # Quick structural check: the scheme byte lives in the first
        # base64 byte after decode.
        import base64
        raw = base64.b64decode(envelope.encode("ascii"))
        assert raw[0] == 0x01, "envelope should be marked encrypted"

        # Decrypt round-trips through to the original plaintext.
        assert memory_vault._decrypt_value("alice", envelope) == b"hello vault"

    def test_encryption_round_trip_unchanged_when_var_false(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "false")
        assert memory_vault._is_encrypted() is True
        envelope = memory_vault._encrypt_value("bob", b"x")
        assert memory_vault._decrypt_value("bob", envelope) == b"x"

    def test_legacy_loose_values_now_keep_encryption_on(
        self, reset_stores, monkeypatch,
    ):
        """A regression of the tightening: a value that previously
        DISABLED encryption (e.g. ``"1"``) must now LEAVE it ON. This
        is the behavioural lift of FIX-P3 — the only way callers see a
        change is if they were relying on the loose parser, which the
        spec explicitly de-supports."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "1")
        # If the loose check had survived, this would be False.
        assert memory_vault._is_encrypted() is True

        envelope = memory_vault._encrypt_value("carol", b"still-encrypted")
        import base64
        raw = base64.b64decode(envelope.encode("ascii"))
        assert raw[0] == 0x01

    def test_plaintext_mode_still_works(self, reset_stores, monkeypatch):
        """The mitigation does NOT block plaintext mode — when
        explicitly opted into via ``"true"``, the existing behaviour
        (scheme byte 0x00, no MAC) is preserved exactly."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        assert memory_vault._is_encrypted() is False

        envelope = memory_vault._encrypt_value("dave", b"plain-bytes")
        import base64
        raw = base64.b64decode(envelope.encode("ascii"))
        assert raw[0] == 0x00, "envelope should be marked plaintext"

        # The round-trip still works.
        assert memory_vault._decrypt_value("dave", envelope) == b"plain-bytes"

    def test_vault_status_reflects_tightened_parse(
        self, reset_stores, monkeypatch,
    ):
        """``vault_status()`` derives its ``encrypted`` flag from
        ``_is_encrypted`` — the tightened parse must flow through to
        the founder-console snapshot."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "1")
        assert memory_vault.vault_status()["encrypted"] is True
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        memory_vault._reset_for_tests()  # clear the one-shot warn flag
        assert memory_vault.vault_status()["encrypted"] is False
