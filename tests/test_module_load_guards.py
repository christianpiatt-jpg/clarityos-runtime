"""
PASS-6 Phase A — Module-load guards.

Simulate fresh-process imports for the three deepest runtime modules
and assert the post-load globals match the documented starting state.
This catches regressions where a module-level mutable state would
silently survive a reload OR where a one-shot side-effect (the
plaintext warning, the founder-default cache) would fire incorrectly
during the simulated reload.

Covered modules:
    * model_router  — _founder_default_model, _founder_default_loaded,
                      _LOCAL_HANDLE_CACHE / _LOCAL_HANDLE_PATH,
                      _PROVIDER_HTTP_TIMEOUT_VAR default
    * operator_state — _HISTORY_SEQ
    * memory_vault  — _MEM_STORE, _KEY_CACHE, _SQLITE_CONN,
                      _PLAINTEXT_WARNING_EMITTED

Each module exposes a ``_reset_for_tests`` (or analogous) hook that
mirrors the post-import state. The tests below call those hooks and
assert the freshly-reset state matches the documented contract — i.e.
no globals reinitialize incorrectly, no plaintext mode flips on, and
the founder default still loads from the vault consistently on the
first call after reset.
"""
from __future__ import annotations

import logging

import pytest

import memory_vault
import model_router as mr
import operator_state


# ===========================================================================
# model_router — post-load globals
# ===========================================================================
class TestModelRouterReloadGuards:
    def test_post_reset_globals_match_documented_defaults(self, reset_stores):
        """After ``_reset_for_tests`` the module-level state is exactly
        what a fresh import would produce. Specifically:
          * No founder default cached.
          * Founder-default loaded flag is False (next get triggers
            a vault lookup).
          * Local-runtime handle cache is empty.
          * ContextVar default equals the runtime_http_config value.
        """
        assert mr._founder_default_model is None
        assert mr._founder_default_loaded is False
        assert mr._LOCAL_HANDLE_CACHE is None
        assert mr._LOCAL_HANDLE_PATH is None

        import runtime_http_config as rhc
        assert mr._PROVIDER_HTTP_TIMEOUT_VAR.get() == rhc.DEFAULT_CALL_TIMEOUT

    def test_founder_default_loads_from_vault_after_reset(self, reset_stores):
        """The persistence guarantee: write a founder default, simulate
        a reload by resetting only the module-level cache, then verify
        the next ``get_founder_default_model`` re-hydrates from the
        vault. This is the V2 contract under a reload cycle."""
        mr.set_founder_default_model("anthropic:claude-haiku-4-5-20251001")
        assert mr.get_founder_default_model() == "anthropic:claude-haiku-4-5-20251001"

        # Simulate process restart — cache cleared, vault preserved.
        mr._founder_default_model = None
        mr._founder_default_loaded = False

        # First call in the "new process" reads from the vault.
        assert mr.get_founder_default_model() == "anthropic:claude-haiku-4-5-20251001"
        assert mr._founder_default_loaded is True

    def test_reset_does_not_resurrect_stale_local_handle(self, reset_stores):
        """If a previous test populated the local handle cache, the
        reset must clear it — otherwise a stale handle could be reused
        when the env path changes."""
        mr._LOCAL_HANDLE_CACHE = object()  # sentinel
        mr._LOCAL_HANDLE_PATH = "/tmp/stale"
        mr._reset_for_tests()
        assert mr._LOCAL_HANDLE_CACHE is None
        assert mr._LOCAL_HANDLE_PATH is None


# ===========================================================================
# operator_state — post-load globals
# ===========================================================================
class TestOperatorStateReloadGuards:
    def test_post_reset_history_seq_is_empty(self, reset_stores):
        """``_HISTORY_SEQ`` is the per-prefix monotonic counter dict.
        After a reset it must be empty so the next call returns 1."""
        # ``_reset_memory_for_tests`` is the operator_state hook
        # invoked by the reset_stores fixture.
        operator_state._reset_memory_for_tests()
        assert operator_state._HISTORY_SEQ == {}
        # And the next call returns 1 — confirming the counter is fresh.
        assert operator_state._next_seq("reload_test") == 1

    def test_seq_lock_remains_pre_allocated_after_reset(self, reset_stores):
        """``_SEQ_LOCK`` is a process-lifetime ``threading.Lock`` —
        ``_reset_memory_for_tests`` must NOT replace or null it
        (otherwise concurrent _next_seq callers would race)."""
        lock_before = operator_state._SEQ_LOCK
        operator_state._reset_memory_for_tests()
        assert operator_state._SEQ_LOCK is lock_before


# ===========================================================================
# memory_vault — post-load globals + plaintext-mode safety
# ===========================================================================
class TestMemoryVaultReloadGuards:
    def test_post_reset_globals_match_documented_defaults(self, reset_stores):
        assert memory_vault._MEM_STORE == {}
        assert memory_vault._KEY_CACHE == {}
        assert memory_vault._SQLITE_CONN is None
        assert memory_vault._SQLITE_PATH_CACHED is None
        assert memory_vault._FIRE_CLIENT is None
        # The PASS-4 FIX-P3 one-shot flag is reset alongside the rest.
        assert memory_vault._PLAINTEXT_WARNING_EMITTED is False

    def test_plaintext_does_not_silently_activate_on_reset(
        self, reset_stores, monkeypatch,
    ):
        """A reset must NOT enable plaintext mode through any side
        channel. We confirm by leaving the env var unset and asserting
        encryption is still on AND no PLAINTEXT warning fires."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        memory_vault._reset_for_tests()
        assert memory_vault._is_encrypted() is True
        # Warning flag must still be False since the warning never fired.
        assert memory_vault._PLAINTEXT_WARNING_EMITTED is False

    def test_loose_legacy_values_do_not_flip_plaintext_on_reset(
        self, reset_stores, monkeypatch,
    ):
        """The PASS-4 FIX-P3 tightening must hold after a reset. If
        the env var carries a legacy value like ``"1"``, the next
        ``_is_encrypted`` call returns True (encryption ON) and the
        plaintext warning does NOT fire."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "1")
        memory_vault._reset_for_tests()
        assert memory_vault._is_encrypted() is True
        assert memory_vault._PLAINTEXT_WARNING_EMITTED is False

    def test_one_shot_warning_re_arms_after_reset(
        self, reset_stores, monkeypatch, caplog,
    ):
        """The PASS-4 FIX-P3 one-shot warning is "per process" — a
        reset re-arms it so a subsequent enable in a simulated new
        process fires the warning again exactly once."""
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")

        # First "process" — warning fires once.
        memory_vault._reset_for_tests()
        for _ in range(5):
            memory_vault._is_encrypted()

        first_burst = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(first_burst) == 1, (
            f"expected 1 warning in first burst, got {len(first_burst)}"
        )

        # Simulate fresh process via reset — flag clears, then re-fires.
        memory_vault._reset_for_tests()
        for _ in range(5):
            memory_vault._is_encrypted()

        total = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(total) == 2, (
            f"expected 2 warnings across both bursts, got {len(total)}"
        )

    def test_key_cache_clears_on_reset(self, reset_stores):
        memory_vault._derive_key("reload_user_a")
        memory_vault._derive_key("reload_user_b")
        assert len(memory_vault._KEY_CACHE) >= 2

        memory_vault._reset_for_tests()
        assert memory_vault._KEY_CACHE == {}


# ===========================================================================
# Cross-module — load-order sanity
# ===========================================================================
class TestCrossModuleLoadOrder:
    """memory_vault is the deepest leaf (no internal imports) and
    operator_state imports memory_vault. After a reset cycle, the
    chain must still work end-to-end with no residue."""

    def test_state_write_after_reset_uses_fresh_vault(self, reset_stores):
        """A reset must produce a coherent state: an operator_state
        write succeeds and lands in the (freshly empty) vault."""
        # Operator-state write → vault put.
        operator_state.record_elins_interaction(
            "reload_xprod", "elins_1",
            context={"topic": "post-reload", "kind": "global"},
        )
        # Vault now has at least the one elins.* entry + the
        # operator_state.* scaffolding fields.
        entries = memory_vault.vault_list("reload_xprod")
        assert any(k.startswith("elins.") for k in entries)
        assert any(k.startswith("operator_state.") for k in entries)

    def test_router_select_after_reset_returns_task_default(self, reset_stores):
        """With no founder default and no user preference, the freshly-
        reset router falls through to the task default — confirming
        no stale founder cache survived the reset."""
        chosen = mr.select_model("reload_xprod", task="ELINS")
        assert chosen == mr.TASK_DEFAULTS["ELINS"]
