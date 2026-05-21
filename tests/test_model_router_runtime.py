"""
PASS-5 Phase D — model_router runtime tests.

Concurrency + multi-instance determinism across BD3 (router).

Covers:
    D1 — Multi-instance founder default consistency
         (process A writes → process B with fresh module globals reads
         the same value from the vault)
    D2 — Per-thread / per-context HTTP timeout isolation under load
         (50 threads, each in its own ``_request_timeout`` block,
         must observe its own value inside ``_http_post_json``)
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import model_router as mr
import memory_vault
import runtime_http_config as rhc


# ===========================================================================
# D1 — Multi-instance founder default consistency
# ===========================================================================
class TestD1FounderDefaultMultiInstance:
    """The founder default model is vault-backed (PASS-4 V2). A fresh
    process must observe the value written by any previous process,
    with no process-global drift between instances."""

    def test_d1_two_simulated_processes_observe_same_default(self, reset_stores):
        """Process A sets the default; Process B (cache cleared, vault
        preserved) must read the same value without ever calling
        ``set_founder_default_model``."""
        # ---- Process A ----
        mr.set_founder_default_model("anthropic:claude-3.7")
        assert mr.get_founder_default_model() == "anthropic:claude-3.7"

        # Confirm it landed in the vault under the synthetic global user.
        stored = memory_vault.vault_get(
            mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
        )
        assert stored == "anthropic:claude-3.7"

        # ---- Process B (fresh import) ----
        # Wipe ONLY the module-level cache; leave the vault row alone.
        # This is exactly what a freshly-cold-started Cloud Run replica
        # sees on import — no in-process cache, but the vault is shared.
        mr._founder_default_model = None
        mr._founder_default_loaded = False

        # First read in the new "process" re-hydrates from the vault.
        assert mr.get_founder_default_model() == "anthropic:claude-3.7"
        assert mr._founder_default_loaded is True

    def test_d1_no_process_global_drift_across_select_model(self, reset_stores):
        """``select_model`` must see the same founder default in the
        new process as the one that was originally set. End-to-end
        check that the precedence chain (founder > preferred_model >
        task default) survives the simulated restart."""
        # ---- Process A: write + verify selection ----
        mr.set_founder_default_model("google:gemini-2.0-flash")
        assert mr.select_model("alice", task="ELINS") == "google:gemini-2.0-flash"

        # ---- Process B: cache reset, vault preserved ----
        mr._founder_default_model = None
        mr._founder_default_loaded = False

        # Process B has never written; the founder default still wins.
        assert mr.select_model("alice", task="ELINS") == "google:gemini-2.0-flash"
        # And task default is correctly bypassed.
        assert mr.select_model("alice", task="ELINS") != mr.TASK_DEFAULTS["ELINS"]

    def test_d1_clearing_default_propagates_to_fresh_process(self, reset_stores):
        """Clearing via ``set_founder_default_model(None)`` must remove
        the vault entry so the next fresh-process read also returns
        None (no stale value resurrection)."""
        mr.set_founder_default_model("openai:gpt-4o")
        assert memory_vault.vault_get(
            mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
        ) == "openai:gpt-4o"

        mr.set_founder_default_model(None)
        assert memory_vault.vault_get(
            mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
        ) is None

        # Fresh-process simulation.
        mr._founder_default_model = None
        mr._founder_default_loaded = False
        assert mr.get_founder_default_model() is None


# ===========================================================================
# D2 — ContextVar timeout isolation under load
# ===========================================================================
class TestD2ContextVarTimeoutUnderLoad:
    """PASS-4 FIX-H6 moved the provider HTTP timeout into a ContextVar.
    Under 50 concurrent threads, each in its own ``_request_timeout``
    block, the snapshot taken inside ``_http_post_json`` must equal
    each thread's own override — never another thread's value."""

    def test_d2_fifty_threads_each_see_own_timeout(
        self, reset_stores, monkeypatch,
    ):
        N = 50
        observed: dict[int, float] = {}
        observed_lock = threading.Lock()
        # Use a barrier so every thread is inside its block when the
        # fake handler reads back the current timeout — without it the
        # threads might serialise and never overlap.
        barrier = threading.Barrier(parties=N)

        def fake_post(url, *, headers, body):
            # Sync with every other thread, then snapshot.
            barrier.wait(timeout=15.0)
            return {"timeout_seen": mr._PROVIDER_HTTP_TIMEOUT}

        monkeypatch.setattr(mr, "_http_post_json", fake_post)

        # Each thread gets a unique float so we can detect any cross-thread
        # contamination at the byte level.
        def worker(idx: int) -> None:
            my_timeout = 1.0 + idx  # 1.0, 2.0, ..., 50.0
            with mr._request_timeout(my_timeout):
                out = mr._http_post_json(
                    "https://example.invalid/x", headers={}, body={},
                )
            with observed_lock:
                observed[idx] = out["timeout_seen"]

        with ThreadPoolExecutor(max_workers=N) as ex:
            futs = [ex.submit(worker, i) for i in range(N)]
            for f in futs:
                f.result(timeout=20.0)

        # Every thread saw its own override — no cross-thread contamination.
        assert len(observed) == N
        for i in range(N):
            assert observed[i] == 1.0 + i, (
                f"thread {i} saw {observed[i]!r} instead of {1.0 + i!r}"
            )

        # After all threads exit, the parent context's default is intact.
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT

    def test_d2_default_restored_after_load(self, reset_stores, monkeypatch):
        """Tighter version of the above — confirm the parent-context
        default is byte-identical to the pre-test value after a burst
        of concurrent overrides exit. Catches a regression where a
        nested ``_request_timeout`` block could miss its ``reset(token)``
        under contention."""
        prior = mr._PROVIDER_HTTP_TIMEOUT

        def fake_post(url, *, headers, body):
            return {"ok": True}

        monkeypatch.setattr(mr, "_http_post_json", fake_post)

        def worker(idx: int) -> None:
            with mr._request_timeout(0.5 + idx):
                mr._http_post_json(
                    "https://example.invalid/x", headers={}, body={},
                )

        with ThreadPoolExecutor(max_workers=50) as ex:
            for f in [ex.submit(worker, i) for i in range(50)]:
                f.result(timeout=20.0)

        assert mr._PROVIDER_HTTP_TIMEOUT == prior

    def test_d2_nested_overrides_restore_lifo_under_load(
        self, reset_stores, monkeypatch,
    ):
        """Each thread enters two nested ``_request_timeout`` blocks
        with different values. LIFO restoration via ``ContextVar.reset``
        must work for every thread without leaking the inner value into
        the outer scope or into any sibling thread."""
        observed: dict[int, tuple[float, float, float]] = {}
        observed_lock = threading.Lock()
        prior = mr._PROVIDER_HTTP_TIMEOUT

        def worker(idx: int) -> None:
            outer = 10.0 + idx
            inner = 100.0 + idx
            with mr._request_timeout(outer):
                seen_outer = mr._PROVIDER_HTTP_TIMEOUT
                with mr._request_timeout(inner):
                    seen_inner = mr._PROVIDER_HTTP_TIMEOUT
                seen_outer_after_inner = mr._PROVIDER_HTTP_TIMEOUT
            with observed_lock:
                observed[idx] = (seen_outer, seen_inner, seen_outer_after_inner)

        with ThreadPoolExecutor(max_workers=50) as ex:
            for f in [ex.submit(worker, i) for i in range(50)]:
                f.result(timeout=20.0)

        assert len(observed) == 50
        for i, (o1, inner, o2) in observed.items():
            assert o1 == 10.0 + i
            assert inner == 100.0 + i
            assert o2 == 10.0 + i, (
                f"thread {i}: outer restoration leaked to {o2!r} after inner"
            )

        # Parent context untouched.
        assert mr._PROVIDER_HTTP_TIMEOUT == prior


# ===========================================================================
# PASS-6 Phase B — B2: Multi-instance determinism for router state
# ===========================================================================
def _simulate_router_instance_reset() -> None:
    """Reset only the router's per-process caches; preserve the vault."""
    import memory_vault
    mr._founder_default_model = None
    mr._founder_default_loaded = False
    mr._LOCAL_HANDLE_CACHE = None
    mr._LOCAL_HANDLE_PATH = None
    # Drop the vault key cache too — it's instance-local; the vault
    # data itself is preserved.
    memory_vault._KEY_CACHE.clear()


class TestB2RouterMultiInstance:
    """Two simulated Cloud Run instances share the same vault. Every
    cross-instance read of router state must converge on the vault as
    the single source of truth — no instance-local drift in founder
    default OR in derived constants like the registry and aliases."""

    def test_b2_founder_default_persists_across_instances(self, reset_stores):
        # ---- Instance A ----
        mr.set_founder_default_model("openai:gpt-4o")
        assert mr.get_founder_default_model() == "openai:gpt-4o"

        # ---- Instance B (fresh) ----
        _simulate_router_instance_reset()
        assert mr.get_founder_default_model() == "openai:gpt-4o"

    def test_b2_select_model_stable_across_instances(self, reset_stores):
        """``select_model`` precedence must produce the same answer in
        both instances given the same vault state. The founder default
        is the only piece of selection state that travels via the
        vault; the rest (task default, preferred_model) does too via
        ``operator_state``."""
        import operator_state

        # ---- Instance A: configure persistent state ----
        mr.set_founder_default_model("anthropic:claude-3.7")
        operator_state.set_preferred_model(
            "b2_select_user", "google:gemini-2.0-flash",
        )
        chosen_a = mr.select_model("b2_select_user", task="ELINS")
        # Founder default wins (precedence step 2).
        assert chosen_a == "anthropic:claude-3.7"

        # ---- Instance B (fresh) ----
        _simulate_router_instance_reset()
        chosen_b = mr.select_model("b2_select_user", task="ELINS")
        assert chosen_b == chosen_a, (
            "INV — select_model drifted across instances"
        )

    def test_b2_no_drift_in_model_registry(self, reset_stores):
        """``MODEL_REGISTRY`` and ``SUPPORTED_MODELS`` are module-level
        constants — they must be byte-identical across simulated
        instance restarts. Catches an accidental mutation that would
        let instance B see a different model catalogue."""
        before_registry = dict(mr.MODEL_REGISTRY)
        before_supported = tuple(mr.SUPPORTED_MODELS)
        before_task_defaults = dict(mr.TASK_DEFAULTS)

        _simulate_router_instance_reset()

        assert mr.MODEL_REGISTRY == before_registry, (
            "INV — MODEL_REGISTRY mutated across instance reset"
        )
        assert mr.SUPPORTED_MODELS == before_supported, (
            "INV — SUPPORTED_MODELS mutated across instance reset"
        )
        assert mr.TASK_DEFAULTS == before_task_defaults, (
            "INV — TASK_DEFAULTS mutated across instance reset"
        )

    def test_b2_no_drift_in_alias_resolution(self, reset_stores):
        """Alias resolution is purely a function of the constant alias
        map — its output must be byte-identical across instances for
        every documented alias."""
        cases = [
            ("claude", "anthropic:claude-3.7"),
            ("CLAUDE", "anthropic:claude-3.7"),
            ("gpt-4o", "openai:gpt-4o"),
            ("gemini", "google:gemini-2.0-flash"),
            ("groq", "xai:groq-llama"),
            ("llama3.1", "local:llama3.1"),
            (None, None),
            ("", None),
            ("unknown_xyz", None),
        ]

        # Instance A.
        before = {alias: mr.resolve_model_alias(alias) for alias, _ in cases}

        _simulate_router_instance_reset()

        # Instance B.
        after = {alias: mr.resolve_model_alias(alias) for alias, _ in cases}
        assert before == after
        # And every result matches the documented expectation.
        for alias, expected in cases:
            assert after[alias] == expected, (
                f"INV — resolve_model_alias({alias!r}) drifted: "
                f"got {after[alias]!r}, expected {expected!r}"
            )

    def test_b2_provider_timeout_default_stable_across_instances(
        self, reset_stores,
    ):
        """The ContextVar's default (the runtime-configured call
        timeout) must be byte-identical after a simulated reset — no
        instance-local drift in the per-context fallback."""
        import runtime_http_config as rhc
        before = mr._PROVIDER_HTTP_TIMEOUT_VAR.get()
        _simulate_router_instance_reset()
        after = mr._PROVIDER_HTTP_TIMEOUT_VAR.get()
        assert before == after == rhc.DEFAULT_CALL_TIMEOUT
