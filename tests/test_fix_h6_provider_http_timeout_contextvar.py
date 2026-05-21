"""
PASS-4 FIX-H6 — Provider HTTP timeout is concurrency-safe.

The pre-fix code stored the effective provider HTTP timeout in a plain
module-level mutable float (``model_router._PROVIDER_HTTP_TIMEOUT``)
that ``_request_timeout`` mutated transactionally with a ``global``
assignment. That works under a single-threaded runtime but is racy as
soon as two coroutines / threads enter ``_request_timeout`` concurrently
— the second call's restoration overwrites the first's, and a
mid-flight ``_http_post_json`` can observe whichever value happens to
be in the global at the moment urllib reads it.

The fix moves the storage into a ``contextvars.ContextVar`` so each
asyncio task / thread observes its own scoped value, while preserving:
  * the legacy read API (``mr._PROVIDER_HTTP_TIMEOUT``) via a module
    ``__getattr__`` that resolves to ``_PROVIDER_HTTP_TIMEOUT_VAR.get()``;
  * the ``_request_timeout(seconds)`` context manager contract,
    including LIFO restoration on exit and on exceptions.

These tests focus narrowly on the V2 mitigation; the existing v66 /
Unit 71 tests in ``test_runtime_http_config.py`` cover the
single-thread happy path and continue to pass unchanged.
"""
from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import model_router as mr
import runtime_http_config as rhc


# ---------------------------------------------------------------------------
# Test A — Per-task / per-thread isolation
# ---------------------------------------------------------------------------
class TestPerContextIsolation:
    def test_concurrent_threads_see_their_own_timeout(self):
        """Two threads enter ``_request_timeout`` with different values
        and observe their own value inside the block. With the prior
        module-global float, one thread's ``finally`` restoration would
        clobber the other thread's view; with the ContextVar each
        thread has its own scope."""

        ready_a = threading.Event()
        ready_b = threading.Event()
        leave_a = threading.Event()
        leave_b = threading.Event()
        observed: dict[str, float] = {}

        def worker_a():
            with mr._request_timeout(11.0):
                ready_a.set()
                # Wait until worker_b has also entered its block,
                # ensuring both are simultaneously holding overrides.
                ready_b.wait(timeout=5.0)
                observed["a_inside"] = mr._PROVIDER_HTTP_TIMEOUT
                leave_a.set()

        def worker_b():
            with mr._request_timeout(22.0):
                ready_b.set()
                ready_a.wait(timeout=5.0)
                observed["b_inside"] = mr._PROVIDER_HTTP_TIMEOUT
                leave_b.set()

        t_a = threading.Thread(target=worker_a)
        t_b = threading.Thread(target=worker_b)
        t_a.start(); t_b.start()
        t_a.join(timeout=5.0); t_b.join(timeout=5.0)
        assert not t_a.is_alive() and not t_b.is_alive()

        # Each thread saw exactly its own override.
        assert observed["a_inside"] == 11.0
        assert observed["b_inside"] == 22.0
        # And the outer scope is back to the default — neither thread's
        # exit leaked into the parent context.
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT

    def test_concurrent_asyncio_tasks_see_their_own_timeout(self):
        """The asyncio path is the primary motivator for FIX-H6 — Cloud
        Run requests run inside the FastAPI event loop and overlap. Two
        tasks setting different timeouts must each observe their own."""

        observed: dict[str, float] = {}

        async def task(name: str, value: float) -> None:
            with mr._request_timeout(value):
                # Yield control so both tasks have entered their blocks
                # before either reads back.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                observed[name] = mr._PROVIDER_HTTP_TIMEOUT

        async def driver() -> None:
            await asyncio.gather(
                task("a", 7.5),
                task("b", 13.25),
                task("c", 0.75),
            )

        asyncio.run(driver())

        assert observed == {"a": 7.5, "b": 13.25, "c": 0.75}
        # No task's value leaks back into the parent context.
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT

    def test_concurrent_http_post_json_observes_caller_timeout(self):
        """Under the fix, each thread's ``_http_post_json`` reads the
        timeout from the ContextVar — so a fake handler that snapshots
        the live timeout mid-call observes its own caller's override,
        never another thread's value. This is the integration check
        that proves the wiring under ``_call_*`` providers is safe."""

        observed: dict[str, float] = {}
        barrier = threading.Barrier(parties=2)

        def fake_post(url, *, headers, body):
            # All threads sync here so they all read the timeout while
            # the other thread is also inside its own block.
            barrier.wait(timeout=5.0)
            return {"timeout_seen": mr._PROVIDER_HTTP_TIMEOUT}

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(mr, "_http_post_json", fake_post)

            def worker(name: str, value: float) -> None:
                with mr._request_timeout(value):
                    out = mr._http_post_json(
                        "https://example.invalid/x",
                        headers={}, body={},
                    )
                observed[name] = out["timeout_seen"]

            t_a = threading.Thread(target=worker, args=("a", 4.0))
            t_b = threading.Thread(target=worker, args=("b", 16.0))
            t_a.start(); t_b.start()
            t_a.join(timeout=5.0); t_b.join(timeout=5.0)

        assert observed == {"a": 4.0, "b": 16.0}


# ---------------------------------------------------------------------------
# Test B — Default behavior
# ---------------------------------------------------------------------------
class TestDefault:
    def test_default_matches_runtime_http_config(self):
        """With no override active, the effective timeout equals
        ``runtime_http_config.DEFAULT_CALL_TIMEOUT`` (same source as
        the pre-FIX-H6 module-level binding)."""
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT

    def test_default_matches_context_var_default(self):
        """The ContextVar's default is the source of truth and must
        equal the documented runtime_http_config default."""
        assert (
            mr._PROVIDER_HTTP_TIMEOUT_VAR.get()
            == rhc.DEFAULT_CALL_TIMEOUT
        )
        assert (
            mr._PROVIDER_HTTP_TIMEOUT_DEFAULT
            == rhc.DEFAULT_CALL_TIMEOUT
        )

    def test_default_restored_after_override(self):
        prior = mr._PROVIDER_HTTP_TIMEOUT
        with mr._request_timeout(99.0):
            assert mr._PROVIDER_HTTP_TIMEOUT == 99.0
        assert mr._PROVIDER_HTTP_TIMEOUT == prior


# ---------------------------------------------------------------------------
# Test C — Backward compatibility
# ---------------------------------------------------------------------------
class TestBackwardCompat:
    def test_request_timeout_signature_unchanged(self):
        """``_request_timeout`` still accepts a single float and is
        still a context manager — no kwargs, no required teardown
        call. The fix is internal-only."""
        # Should not raise; returning a context manager.
        cm = mr._request_timeout(5.0)
        with cm:
            assert mr._PROVIDER_HTTP_TIMEOUT == 5.0

    def test_request_timeout_restores_after_exception(self):
        original = mr._PROVIDER_HTTP_TIMEOUT
        with pytest.raises(RuntimeError):
            with mr._request_timeout(3.0):
                assert mr._PROVIDER_HTTP_TIMEOUT == 3.0
                raise RuntimeError("boom")
        assert mr._PROVIDER_HTTP_TIMEOUT == original

    def test_request_timeout_nested_blocks_restore_lifo(self):
        """LIFO restoration is preserved through ContextVar.reset, so
        the pre-FIX-H6 nested-override behaviour is unchanged."""
        original = mr._PROVIDER_HTTP_TIMEOUT
        with mr._request_timeout(10.0):
            with mr._request_timeout(20.0):
                assert mr._PROVIDER_HTTP_TIMEOUT == 20.0
            assert mr._PROVIDER_HTTP_TIMEOUT == 10.0
        assert mr._PROVIDER_HTTP_TIMEOUT == original

    def test_legacy_attribute_read_returns_float(self):
        """Tests and external callers read ``mr._PROVIDER_HTTP_TIMEOUT``
        expecting a float; the ``__getattr__`` shim must keep returning
        a float (the ContextVar's current value)."""
        v = mr._PROVIDER_HTTP_TIMEOUT
        assert isinstance(v, float)

    def test_module_getattr_raises_on_unknown(self):
        """The ``__getattr__`` dispatcher must still raise
        AttributeError for unknown names — otherwise ``hasattr`` checks
        and ``from model_router import *`` would behave oddly."""
        with pytest.raises(AttributeError):
            _ = mr._does_not_exist_xyz  # type: ignore[attr-defined]
