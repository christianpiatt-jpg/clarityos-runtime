"""
PASS-4 V2 — Founder default model is vault-backed.

Verifies that ``model_router._founder_default_model`` is no longer a
process-local-only variable: the value is persisted to the per-user
memory vault under the synthetic ``__founder_global__`` user_id and key
``founder_global.default_model`` so every process / instance converges
on the same value on first use.

The existing v44 model_router tests (test_v44_model_router.py) continue
to cover the selection precedence and validation surface. These tests
focus narrowly on the persistence guarantee added by the V2 mitigation:

* Test A — Persistence:
    set the founder default, simulate a fresh process by wiping only
    the in-process cache, confirm the next read returns the stored
    value from the vault.

* Test B — Fallback:
    with the vault cleared of ``founder_global.default_model``,
    ``get_founder_default_model`` returns None and ``select_model``
    falls through to the existing task-default chain.

* Test C — Multi-instance consistency:
    Process 1 sets the value and writes through to the vault;
    Process 2 boots fresh (cache wiped, vault preserved) and reads the
    same value.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _simulate_fresh_process(mr) -> None:
    """Wipe ONLY the model_router process-local cache for the founder
    default; the vault entry persists. This is the read path that a
    fresh process would execute when ``get_founder_default_model`` is
    called for the first time after import."""
    mr._founder_default_model = None
    mr._founder_default_loaded = False


# ---------------------------------------------------------------------------
# Test A — Persistence
# ---------------------------------------------------------------------------
def test_founder_default_persists_across_simulated_process_restart(reset_stores):
    """After ``set_founder_default_model``, a fresh process (cache
    cleared, vault untouched) must read the same value back from the
    vault."""
    import model_router as mr
    import memory_vault

    # Sanity: clean slate from the reset_stores fixture.
    assert mr.get_founder_default_model() is None

    # Set + verify the in-process cache reflects the new value.
    mr.set_founder_default_model("openai:gpt-5.4")
    assert mr.get_founder_default_model() == "openai:gpt-5.4"

    # The vault is the source of truth — confirm the entry landed.
    stored = memory_vault.vault_get(
        mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
    )
    assert stored == "openai:gpt-5.4"

    # Simulate process restart by clearing the in-process cache only.
    # The vault entry is left alone — mirrors what a new Cloud Run
    # replica sees on cold start after a previous instance wrote.
    _simulate_fresh_process(mr)
    assert mr._founder_default_model is None
    assert mr._founder_default_loaded is False

    # First call in the "new process" re-hydrates from the vault.
    assert mr.get_founder_default_model() == "openai:gpt-5.4"
    assert mr._founder_default_loaded is True


# ---------------------------------------------------------------------------
# Test B — Fallback to hard-coded task default when vault is empty
# ---------------------------------------------------------------------------
def test_founder_default_falls_back_to_task_default_when_vault_empty(reset_stores):
    """With no founder_global.default_model in the vault, the router
    must behave exactly as if no founder override was set: select_model
    falls through to the user pref / task default chain."""
    import model_router as mr
    import memory_vault

    # Defensive — ensure the vault really is empty for this key.
    memory_vault.vault_delete(
        mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
    )
    _simulate_fresh_process(mr)

    # get_founder_default_model returns None on empty vault.
    assert mr.get_founder_default_model() is None

    # select_model falls through to TASK_DEFAULTS for every task bucket.
    for task in ("c", "ELINS", "macro", "regional"):
        assert mr.select_model(None, task=task) == mr.TASK_DEFAULTS[task]


def test_founder_default_clear_with_none_removes_vault_entry(reset_stores):
    """Setting the founder default to None must delete the vault entry
    so a subsequent fresh-process read also returns None (no stale
    value resurrecting through the cache)."""
    import model_router as mr
    import memory_vault

    mr.set_founder_default_model("anthropic:claude-haiku-4-5-20251001")
    assert memory_vault.vault_get(
        mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
    ) == "anthropic:claude-haiku-4-5-20251001"

    mr.set_founder_default_model(None)
    assert memory_vault.vault_get(
        mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
    ) is None

    _simulate_fresh_process(mr)
    assert mr.get_founder_default_model() is None


# ---------------------------------------------------------------------------
# Test C — Multi-instance consistency
# ---------------------------------------------------------------------------
def test_founder_default_multi_instance_consistency(reset_stores):
    """Two simulated processes share the vault. Process 1 sets a value;
    Process 2 (fresh import / cache cleared, vault preserved) reads the
    same value without ever calling ``set_founder_default_model``."""
    import model_router as mr

    # ---- Process 1 ----
    mr.set_founder_default_model("google:gemini-2.5-flash")
    assert mr.get_founder_default_model() == "google:gemini-2.5-flash"
    # Confirm select_model picks it up (precedence step 2).
    assert mr.select_model("alice", task="c") == "google:gemini-2.5-flash"

    # ---- Process 2 (fresh) ----
    # Wipe only the model_router cache — leave the vault intact, which
    # is the state a freshly-cold-started replica observes.
    _simulate_fresh_process(mr)

    # Process 2 has never called set_founder_default_model; the vault
    # is the only place the value lives.
    assert mr.get_founder_default_model() == "google:gemini-2.5-flash"

    # And select_model uses the same precedence on the fresh side,
    # without any in-process state ever having been written.
    assert mr.select_model("alice", task="ELINS") == "google:gemini-2.5-flash"


def test_founder_default_validation_unchanged(reset_stores):
    """Existing v44 contract — unknown model_id must still raise. The
    vault-backed implementation must not weaken this check (otherwise
    an invalid value could land in the vault and break subsequent
    processes)."""
    import model_router as mr
    with pytest.raises(ValueError):
        mr.set_founder_default_model("not_a_model")


def test_founder_default_namespace_registered(reset_stores):
    """The vault must accept ``founder_global.*`` keys. Belt-and-braces
    check so a future refactor that drops the namespace from
    ALLOWED_NAMESPACES fails loudly here instead of at runtime in
    set_founder_default_model."""
    import memory_vault
    assert "founder_global" in memory_vault.ALLOWED_NAMESPACES
