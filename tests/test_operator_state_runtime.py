"""
PASS-5 Phase D — operator_state runtime tests.

Concurrency + determinism across BD4 (state).

Covers:
    D3 — ``_next_seq`` determinism under concurrency
         (50 concurrent calls must return 50 unique, strictly
         increasing integers — no duplicates, no race-induced gaps,
         no contamination across prefixes.)
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import operator_state


# ===========================================================================
# D3 — _next_seq determinism under concurrency
# ===========================================================================
class TestD3NextSeqUnderConcurrency:
    """``operator_state._next_seq(prefix)`` is the per-prefix
    monotonic counter that produces unique vault keys for ELINS / #G
    history entries. It's protected by ``_SEQ_LOCK``; under 50
    concurrent calls every returned value must be unique and the
    multiset must equal ``{1..50}``."""

    def test_d3_single_prefix_fifty_threads_unique_strictly_increasing(
        self, reset_stores,
    ):
        N = 50
        results: list[int] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker() -> None:
            # All threads release together so the contention is maximal
            # and any race in the lock would be reliably triggered.
            barrier.wait(timeout=10.0)
            seq = operator_state._next_seq("test")
            with results_lock:
                results.append(seq)

        with ThreadPoolExecutor(max_workers=N) as ex:
            futs = [ex.submit(worker) for _ in range(N)]
            for f in futs:
                f.result(timeout=10.0)

        # Exactly N values returned.
        assert len(results) == N
        # All unique — set size matches list size.
        assert len(set(results)) == N
        # Sorted form is the contiguous range {1..N} — no gaps, no
        # duplicates, no values outside the expected window.
        assert sorted(results) == list(range(1, N + 1))

    def test_d3_batched_concurrent_calls_remain_unique(self, reset_stores):
        """Each thread pulls a batch of M ids. After all threads
        complete, the multiset of ids equals ``{1..T*M}`` — every id
        appears exactly once and the counter never lost an increment
        under sustained contention."""
        T = 10   # threads
        M = 25   # ids per thread
        results: list[int] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=T)

        def worker() -> None:
            barrier.wait(timeout=10.0)
            local = [operator_state._next_seq("test") for _ in range(M)]
            with results_lock:
                results.extend(local)

        with ThreadPoolExecutor(max_workers=T) as ex:
            for f in [ex.submit(worker) for _ in range(T)]:
                f.result(timeout=10.0)

        assert len(results) == T * M
        assert sorted(results) == list(range(1, T * M + 1))

    def test_d3_distinct_prefixes_have_independent_counters(self, reset_stores):
        """Two prefixes (``elins`` and ``g_runs``-style) advance
        independently — concurrent calls on prefix A must not consume
        seq values from prefix B, and vice versa."""
        N = 50
        results_a: list[int] = []
        results_b: list[int] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N * 2)

        def worker(prefix: str, bucket: list[int]) -> None:
            barrier.wait(timeout=10.0)
            seq = operator_state._next_seq(prefix)
            with results_lock:
                bucket.append(seq)

        with ThreadPoolExecutor(max_workers=N * 2) as ex:
            futs = []
            for _ in range(N):
                futs.append(ex.submit(worker, "elins.", results_a))
                futs.append(ex.submit(worker, "g_runs.", results_b))
            for f in futs:
                f.result(timeout=10.0)

        assert sorted(results_a) == list(range(1, N + 1))
        assert sorted(results_b) == list(range(1, N + 1))

    def test_d3_no_gaps_beyond_concurrency_interleaving(self, reset_stores):
        """A focused gap-check: the seq values returned by 50 threads
        cover the consecutive range with no missing integers. A race
        that lost an increment would manifest as a gap (e.g. one
        value of 49 returned twice, the value 50 never returned)."""
        N = 50
        results = set()
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker() -> None:
            barrier.wait(timeout=10.0)
            seq = operator_state._next_seq("test")
            with results_lock:
                # If a duplicate slipped through, the set would have
                # fewer than N entries after the bulk run.
                results.add(seq)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker) for _ in range(N)]:
                f.result(timeout=10.0)

        assert results == set(range(1, N + 1)), (
            f"missing or extra seq values: "
            f"unexpected={sorted(results - set(range(1, N + 1)))} "
            f"missing={sorted(set(range(1, N + 1)) - results)}"
        )

    def test_d3_seq_lock_remains_usable_after_load(self, reset_stores):
        """``_SEQ_LOCK`` must still be a usable lock after the burst —
        i.e. the lock state is healthy and not stuck held by a thread
        that exited mid-acquire. Catches any regression that could
        leave the lock in a wedged state.

        Note: ``_SEQ_LOCK`` is a non-reentrant ``threading.Lock``, so
        this test checks acquirability via ``acquire(blocking=False)``
        followed by a release — it does NOT nest a ``_next_seq`` call
        inside a ``with _SEQ_LOCK:`` block (that would self-deadlock).
        """
        N = 50
        barrier = threading.Barrier(parties=N)

        def worker() -> None:
            barrier.wait(timeout=10.0)
            operator_state._next_seq("test")

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker) for _ in range(N)]:
                f.result(timeout=10.0)

        # The lock is acquirable — non-blocking attempt succeeds, then
        # we release immediately so the next _next_seq call works.
        acquired = operator_state._SEQ_LOCK.acquire(blocking=False)
        assert acquired, "_SEQ_LOCK is wedged after the concurrent burst"
        operator_state._SEQ_LOCK.release()

        # And the counter resumes cleanly on a fresh prefix.
        n_after = operator_state._next_seq("after_load")
        assert n_after == 1  # new prefix, new counter starting at 1


# ===========================================================================
# PASS-6 Phase B — B2: Multi-instance determinism for operator_state
# ===========================================================================
def _simulate_state_instance_reset() -> None:
    """Reset operator_state's per-process counter; preserve the
    vault. The persistent operator-state lives entirely under the
    ``operator_state.*`` and ``elins.*`` / ``g_runs.*`` vault keys,
    which survive the reset because the vault backend itself is
    untouched."""
    import memory_vault
    operator_state._HISTORY_SEQ.clear()
    # Drop the vault's key cache too; the persistent _MEM_STORE is
    # what carries state across instances.
    memory_vault._KEY_CACHE.clear()


class TestB2OperatorStateMultiInstance:
    """Two simulated instances share the same vault. State written by
    instance A must be readable by instance B via ``get_operator_state``
    — the vault is the single source of truth, not any module-level
    cache."""

    def test_b2_operator_state_persists_across_instances(self, reset_stores):
        # ---- Instance A: write the full state surface ----
        operator_state.set_external_signal_mode(
            "b2_persist_user", "cloud_perplexity",
        )
        operator_state.set_preferred_model(
            "b2_persist_user", "openai:gpt-5.4",
        )
        operator_state.record_model_used(
            "b2_persist_user", "anthropic:claude-haiku-4-5-20251001",
        )
        operator_state.record_elins_interaction(
            "b2_persist_user", "elins_a",
            context={"topic": "trust", "kind": "global"},
        )
        operator_state.record_g_run(
            "b2_persist_user", "g_a",
            context={"mode": "G", "topic": "g-topic"},
        )

        state_a = operator_state.get_operator_state("b2_persist_user")

        # ---- Instance B (fresh per-process state, same vault) ----
        _simulate_state_instance_reset()
        state_b = operator_state.get_operator_state("b2_persist_user")

        # Every persistent field is preserved byte-for-byte.
        assert state_b["external_signal_mode"]    == state_a["external_signal_mode"]
        assert state_b["preferred_model"]         == state_a["preferred_model"]
        assert state_b["last_model_used"]         == state_a["last_model_used"]
        assert state_b["elins_history"]           == state_a["elins_history"]
        assert state_b["g_history"]               == state_a["g_history"]
        assert state_b["preferred_regions"]       == state_a["preferred_regions"]
        assert state_b["preferred_domains"]       == state_a["preferred_domains"]

    def test_b2_seq_counter_resets_per_instance_but_keys_remain_unique(
        self, reset_stores,
    ):
        """The per-process ``_HISTORY_SEQ`` counter starts from 1 on
        each instance. Vault keys for history entries combine
        ``ts_ms`` + ``seq``, so two instances writing at exactly the
        same millisecond AND same seq would collide. In practice,
        the timestamp differs; this test confirms instance B's
        counter is independent and starts cleanly."""
        # Instance A: write 5 history entries.
        for i in range(5):
            operator_state.record_elins_interaction(
                "b2_seq_user", f"elins_{i}",
                context={"topic": f"t_{i}", "kind": "global"},
            )
        a_seq_after = dict(operator_state._HISTORY_SEQ)

        _simulate_state_instance_reset()

        # Instance B: counter is empty post-reset.
        assert operator_state._HISTORY_SEQ == {}
        # And new writes start from 1.
        operator_state.record_elins_interaction(
            "b2_seq_user", "elins_5_after_restart",
            context={"topic": "post", "kind": "global"},
        )
        # The new seq counter is 1.
        assert operator_state._HISTORY_SEQ.get("elins.") == 1
        # And instance A's counter is gone — confirming independence.
        assert operator_state._HISTORY_SEQ != a_seq_after

    def test_b2_strip_forbidden_applies_after_instance_reset(
        self, reset_stores,
    ):
        """The redaction guarantee must hold across instance
        boundaries — instance B's writes are still scrubbed even
        though the in-process state was fully reset."""
        _simulate_state_instance_reset()
        operator_state.record_elins_interaction(
            "b2_strip_user", "elins_b",
            context={
                "topic": "post-restart",
                "text": "PROMPT BODY SHOULD NOT LEAK",
                "scenario_text": "also forbidden",
                "kind": "global",
            },
        )
        # Walk the vault directly — forbidden fields cannot have landed.
        import memory_vault
        entries = memory_vault.vault_list("b2_strip_user")
        for k, entry in entries.items():
            if not k.startswith("elins.") or not isinstance(entry, dict):
                continue
            for forbidden in (
                "text", "scenario_text", "input_text", "raw_text",
            ):
                assert forbidden not in entry

    def test_b2_history_max_holds_across_instance_boundary(
        self, reset_stores,
    ):
        """If instance A wrote up to the cap and instance B continues
        writing, the total still doesn't exceed HISTORY_MAX — the
        prune happens on every record_* call so it survives the
        in-process state reset."""
        cap = operator_state.HISTORY_MAX

        # Instance A writes cap - 10 entries.
        for i in range(cap - 10):
            operator_state.record_elins_interaction(
                "b2_cap_user", f"elins_{i}",
                context={"topic": f"t_{i}", "kind": "global"},
            )

        _simulate_state_instance_reset()

        # Instance B writes 20 more — total would be cap + 10 without
        # pruning. After the prune, exactly cap remain.
        for i in range(20):
            operator_state.record_elins_interaction(
                "b2_cap_user", f"elins_post_{i}",
                context={"topic": f"p_{i}", "kind": "global"},
            )

        import memory_vault
        entries = memory_vault.vault_list("b2_cap_user")
        elins_count = sum(1 for k in entries if k.startswith("elins."))
        assert elins_count == cap, (
            f"INV-S2 violated across instance boundary — "
            f"persisted {elins_count} rows, expected cap={cap}"
        )
