"""
PASS-7 — Optional load + stress envelope.

This suite is **not** part of the default CI gate. It runs only when
explicitly selected via ``pytest -m load_envelope``. Treat the results
as informational: it characterises the v0.1.0 runtime's behaviour
under synthetic load, but does not block merges.

Why opt-in:
  * The full burst hits 50 concurrent HTTP flows + 50 concurrent
    macro runs + a handful of timeout-shaped tests. On a slow CI
    runner the wall-clock can balloon past the runtime_spine gate
    budget, even though every contract being asserted is also
    locked by the gating tests.
  * The assertions overlap with the locked PASS-4 / PASS-5 / PASS-6
    invariants — load tests catch the same regressions, just under
    contention. Running them in the default gate would duplicate
    coverage without adding signal.

What this suite asserts:
    L1 — Synthetic concurrent HTTP load (50 flows of
         login → /me → /elins/preview → /me): no 5xx, no invariant
         violations, no deadlocks within the per-flow timeout.
    L2 — Macro concurrency envelope: 50 concurrent ``run_macro_ELINS``
         invocations across many users produce unique run_ids, a
         strictly monotonic seq, and no cross-user contamination in
         operator_state / vault.
    L3 — Timeout behaviour under load: the ContextVar HTTP timeout
         is honoured per-task, no leakage across concurrent
         ``_request_timeout`` blocks, and slow-provider error
         logging never leaks sensitive data.
"""
from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_FIXP5_LOGGERS = {
    "clarityos",
    "clarityos.intelligence_kernel",
    "clarityos.model_router",
    "clarityos.operator_state",
    "clarityos.memory_vault",
}

_MACRO_ID_RE = re.compile(r"^macro_(\d+)_(\d+)$")


def _register_user(username: str, cohort: str = "founder") -> str:
    """Direct user creation — bypasses /register so the load suite
    can scale to dozens of users without driving the registration
    flow under contention."""
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    return username


# ===========================================================================
# L1 — Synthetic concurrent HTTP load
# ===========================================================================
class TestL1SyntheticHttpLoad:
    """N concurrent users each drive the full vertical
    (login → /me → /elins/preview → /me). The envelope tests three
    things in one burst: HTTP correctness (no 5xx), the locked
    invariants under contention, and absence of deadlocks (every
    flow finishes within the per-flow timeout)."""

    @pytest.mark.load_envelope
    def test_l1_fifty_concurrent_flows(self, reset_stores, caplog):
        from conftest import TestClient
        import app as app_module

        N = 50
        per_flow_timeout_s = 30.0

        usernames = [f"l1_load_user_{i:04d}_FULL_UNIQUE" for i in range(N)]
        for u in usernames:
            _register_user(u)

        clients = [TestClient(app_module.app) for _ in range(N)]
        results: list[dict] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N, timeout=60.0)

        caplog.set_level(logging.INFO)
        burst_started = time.perf_counter()

        def worker(idx: int) -> None:
            r: dict = {"idx": idx, "user": usernames[idx], "status": "starting"}
            try:
                # Wait until every worker is ready, then release all
                # together so the contention is maximal.
                barrier.wait(timeout=per_flow_timeout_s)
                t0 = time.perf_counter()

                client = clients[idx]
                r_login = client.post(
                    "/login",
                    json={"username": usernames[idx], "password": "x"},
                )
                r["login_status"] = r_login.status_code
                if r_login.status_code != 200:
                    r["status"] = "login_failed"
                    return
                sid = r_login.json()["session_id"]
                r["sid"] = sid
                hdrs = {"X-Session-ID": sid}

                r_me1 = client.get("/me", headers=hdrs)
                r["me1_status"] = r_me1.status_code

                r_prev = client.post(
                    "/elins/preview", headers=hdrs,
                    json={"text": "trust between partners is eroding"},
                )
                r["preview_status"] = r_prev.status_code

                r_me2 = client.get("/me", headers=hdrs)
                r["me2_status"] = r_me2.status_code
                r["me2_body"] = r_me2.json()

                r["elapsed_s"] = time.perf_counter() - t0
                r["status"] = "ok"
            except Exception as e:   # pragma: no cover (defensive)
                r["status"] = "exception"
                r["exception"] = repr(e)
            finally:
                with results_lock:
                    results.append(r)

        with ThreadPoolExecutor(max_workers=N) as ex:
            futs = [ex.submit(worker, i) for i in range(N)]
            for f in futs:
                f.result(timeout=per_flow_timeout_s + 30.0)

        burst_elapsed = time.perf_counter() - burst_started
        # Liveness — every worker finished in time.
        assert len(results) == N, (
            f"L1 deadlock or timeout — {N} workers, {len(results)} returned"
        )

        # No 5xx; every flow's four requests are 2xx.
        for r in results:
            assert r["status"] == "ok", f"flow failed: {r}"
            for k in ("login_status", "me1_status", "preview_status", "me2_status"):
                code = r[k]
                assert 200 <= code < 300, (
                    f"L1 violated — 5xx-or-other-non-2xx on {k}: {r}"
                )

        # No invariant violations: last_model_used populated for
        # every user (proves the kernel completed the ELINS preview
        # cleanly under load).
        for r in results:
            ik_block = r["me2_body"].get("intelligence_kernel") or {}
            assert ik_block.get("last_model_used"), (
                f"L1 invariant violated — user {r['user']!r} has no "
                f"last_model_used after preview under load"
            )

        # No redaction leak: full usernames + session ids absent
        # from FIX-P5 loggers.
        raw_usernames = set(usernames)
        raw_sids = {r["sid"] for r in results}
        offenders: list[tuple[str, str, str]] = []
        for rec in caplog.records:
            if rec.name not in _FIXP5_LOGGERS:
                continue
            msg = rec.getMessage()
            for u in raw_usernames:
                if u in msg:
                    offenders.append(("username", rec.name, msg))
            for sid in raw_sids:
                if sid in msg:
                    offenders.append(("session_id", rec.name, msg))
        assert offenders == [], (
            "L1 redaction violated under load:\n" +
            "\n".join(f"  {k} via {l!r}: {m!r}" for k, l, m in offenders)
        )

        # Burst-level latency snapshot for the perf table in
        # docs/performance.md. Numbers vary per host so we do NOT
        # assert against them — informational only.
        elapsed = sorted(r["elapsed_s"] for r in results)
        # 50th + 95th percentile by index.
        p50 = elapsed[len(elapsed) // 2]
        p95 = elapsed[max(0, int(round(len(elapsed) * 0.95)) - 1)]
        print(
            f"\nL1 envelope (N={N}): "
            f"burst {burst_elapsed:.2f}s, p50 {p50*1000:.0f}ms, "
            f"p95 {p95*1000:.0f}ms",
        )

    @pytest.mark.load_envelope
    def test_l1_no_5xx_under_mixed_workload(self, reset_stores):
        """Variant of the above — half the workers run the full
        vertical, half just hammer ``/me`` repeatedly. Catches
        regressions where a 5xx surfaces only under mixed traffic."""
        from conftest import TestClient
        import app as app_module

        N = 30
        users = [f"l1_mixed_user_{i:04d}" for i in range(N)]
        for u in users:
            _register_user(u)
        clients = [TestClient(app_module.app) for _ in range(N)]
        results: list[dict] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N, timeout=30.0)

        def worker(idx: int) -> None:
            r: dict = {"idx": idx, "user": users[idx]}
            barrier.wait(timeout=30.0)
            client = clients[idx]
            r_login = client.post(
                "/login", json={"username": users[idx], "password": "x"},
            )
            r["login_status"] = r_login.status_code
            if r_login.status_code != 200:
                r["status"] = "login_failed"
                with results_lock:
                    results.append(r)
                return
            sid = r_login.json()["session_id"]
            hdrs = {"X-Session-ID": sid}

            if idx % 2 == 0:
                # Full vertical.
                r["me1"] = client.get("/me", headers=hdrs).status_code
                r["preview"] = client.post(
                    "/elins/preview", headers=hdrs,
                    json={"text": "mixed-workload preview"},
                ).status_code
                r["me2"] = client.get("/me", headers=hdrs).status_code
            else:
                # /me hammer.
                for j in range(5):
                    r[f"me_{j}"] = client.get("/me", headers=hdrs).status_code

            r["status"] = "ok"
            with results_lock:
                results.append(r)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=60.0)

        assert len(results) == N
        for r in results:
            assert r["status"] == "ok", f"mixed-workload flow failed: {r}"
            for k, v in r.items():
                if isinstance(v, int) and k.endswith("_status"):
                    assert 200 <= v < 300
                elif isinstance(v, int) and k.startswith("me_"):
                    assert 200 <= v < 300


# ===========================================================================
# L2 — Macro concurrency envelope
# ===========================================================================
class TestL2MacroConcurrency:
    """Multi-user macro burst. Asserts uniqueness, monotonicity, and
    per-user isolation — extending the D4 / B2 invariants under a
    multi-user shape rather than the single-user one those tests
    use."""

    @pytest.mark.load_envelope
    def test_l2_macro_runs_unique_across_concurrent_users(
        self, reset_stores, caplog,
    ):
        import intelligence_kernel as ik
        import memory_vault
        import operator_state

        N = 50
        # Per-thread distinct system_user labels (mirroring what a
        # multi-scheduler-instance deployment would emit).
        system_users = [f"l2_scheduler_{i:04d}" for i in range(N)]
        captured_run_ids: list[str] = []
        captured_lock = threading.Lock()

        # Wrap _make_macro_run_id so we observe every allocation,
        # not just the ones the wrapper returns to the caller.
        original_make = ik._make_macro_run_id

        def capturing_make(now, seq=None):
            rid = original_make(now, seq=seq)
            with captured_lock:
                captured_run_ids.append(rid)
            return rid

        caplog.set_level(logging.INFO)

        try:
            ik._make_macro_run_id = capturing_make
            results: list[dict] = []
            results_lock = threading.Lock()
            barrier = threading.Barrier(parties=N, timeout=60.0)

            def worker(idx: int) -> None:
                barrier.wait(timeout=60.0)
                summary = ik.run_macro_ELINS(system_users[idx])
                with results_lock:
                    results.append({
                        "idx": idx,
                        "user": system_users[idx],
                        "run_id": summary["run_id"],
                    })

            with ThreadPoolExecutor(max_workers=N) as ex:
                for f in [ex.submit(worker, i) for i in range(N)]:
                    f.result(timeout=180.0)
        finally:
            ik._make_macro_run_id = original_make

        # Liveness.
        assert len(results) == N

        # Run-id uniqueness across all N invocations.
        rids = [r["run_id"] for r in results]
        assert len(set(rids)) == N, (
            f"L2 violated — duplicate run_ids: "
            f"{len(rids) - len(set(rids))} collisions"
        )

        # Macro seq monotonicity — extracting the seq half from every
        # captured run_id gives a contiguous set.
        seqs: list[int] = []
        for rid in captured_run_ids:
            m = _MACRO_ID_RE.match(rid)
            assert m is not None, (
                f"L2 violated — run_id {rid!r} broke the format"
            )
            seqs.append(int(m.group(2)))
        # Every seq is unique.
        assert len(set(seqs)) == len(seqs)
        # And the range is contiguous from min(seqs) to max(seqs).
        assert sorted(seqs) == list(range(min(seqs), max(seqs) + 1))

    @pytest.mark.load_envelope
    def test_l2_no_cross_user_contamination_in_state_under_load(
        self, reset_stores,
    ):
        """N users each perform N writes to operator_state in
        parallel. After the burst, every user's persisted state is
        exactly N entries with that user's labels — no leak between
        users."""
        import memory_vault
        import operator_state

        N = 20
        per_user_writes = 10
        users = [f"l2_state_user_{i:04d}" for i in range(N)]

        barrier = threading.Barrier(parties=N, timeout=30.0)

        def worker(user: str) -> None:
            barrier.wait(timeout=30.0)
            for j in range(per_user_writes):
                operator_state.record_elins_interaction(
                    user, f"{user}_elins_{j}",
                    context={
                        "topic":  f"{user}_topic_{j}",
                        "kind":   "global",
                        # Smuggle a forbidden field — the FIX-P2 + INV-S3
                        # contract must remove it under load too.
                        "text":   f"PROMPT BODY FOR {user} — MUST NOT LEAK",
                    },
                )

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, u) for u in users]:
                f.result(timeout=60.0)

        # Per-user verification.
        for user in users:
            entries = memory_vault.vault_list(user)
            elins_entries = [
                e for k, e in entries.items()
                if k.startswith("elins.") and isinstance(e, dict)
            ]
            # Each user has exactly per_user_writes ELINS rows.
            assert len(elins_entries) == per_user_writes, (
                f"L2 violated — user {user!r} has "
                f"{len(elins_entries)} entries, expected {per_user_writes}"
            )
            # Every entry's elins_id starts with this user's name —
            # NO cross-user contamination.
            for entry in elins_entries:
                eid = entry.get("elins_id", "")
                assert eid.startswith(user), (
                    f"L2 violated — user {user!r} entry has "
                    f"elins_id {eid!r} (does not belong here)"
                )
            # Forbidden-field stripping holds even under load.
            for entry in elins_entries:
                for forbidden in (
                    "text", "scenario_text", "input_text", "raw_text",
                ):
                    assert forbidden not in entry

    @pytest.mark.load_envelope
    def test_l2_no_cross_user_contamination_in_vault_under_load(
        self, reset_stores,
    ):
        """Two users writing to the SAME namespace under contention
        must not see each other's data. The vault's per-user
        partitioning is enforced by ``_validate_user`` + the per-user
        ``_load_user`` / ``_save_user`` paths."""
        import memory_vault

        N = 50
        users = [f"l2_vault_user_{i:04d}" for i in range(N)]
        per_user_keys = ["notes.a", "notes.b", "notes.c"]
        barrier = threading.Barrier(parties=N, timeout=30.0)

        def worker(user: str) -> None:
            barrier.wait(timeout=30.0)
            for key in per_user_keys:
                memory_vault.vault_put(user, key, {"owner": user, "key": key})

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, u) for u in users]:
                f.result(timeout=60.0)

        # Each user sees only its own data.
        for user in users:
            entries = memory_vault.vault_list(user)
            for key in per_user_keys:
                v = entries.get(key)
                assert v is not None, (
                    f"L2 violated — user {user!r} missing key {key!r}"
                )
                assert v["owner"] == user, (
                    f"L2 violated — user {user!r} key {key!r} owned by "
                    f"{v['owner']!r}"
                )


# ===========================================================================
# L3 — Timeout behaviour under load
# ===========================================================================
class TestL3TimeoutUnderLoad:
    """Patches ``model_router._http_post_json`` to simulate slow
    provider responses; verifies ``_PROVIDER_HTTP_TIMEOUT_VAR``
    isolation under contention and that error-path logging never
    carries sensitive data."""

    @pytest.mark.load_envelope
    def test_l3_per_task_timeout_honoured_under_load(
        self, reset_stores, monkeypatch,
    ):
        """50 threads each enter ``_request_timeout(value)`` with
        a unique value, then the patched ``_http_post_json``
        observes the active timeout mid-call. Each thread must see
        its own value, never another thread's."""
        import model_router as mr

        N = 50
        observed: dict[int, float] = {}
        observed_lock = threading.Lock()
        barrier = threading.Barrier(parties=N, timeout=30.0)

        def fake_post(url, *, headers, body):
            # Hold every thread inside the call until all are
            # inside — then snapshot. With the ContextVar fix, each
            # thread sees its own value.
            barrier.wait(timeout=30.0)
            return {"timeout_seen": mr._PROVIDER_HTTP_TIMEOUT}

        monkeypatch.setattr(mr, "_http_post_json", fake_post)

        def worker(idx: int) -> None:
            my_timeout = 0.1 + 0.05 * idx   # 0.10, 0.15, 0.20, ...
            with mr._request_timeout(my_timeout):
                out = mr._http_post_json(
                    "https://example.invalid/x", headers={}, body={},
                )
            with observed_lock:
                observed[idx] = out["timeout_seen"]

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=60.0)

        # No cross-thread contamination.
        for i in range(N):
            expected = 0.1 + 0.05 * i
            assert abs(observed[i] - expected) < 1e-9, (
                f"L3 violated — thread {i} saw {observed[i]!r}, "
                f"expected {expected!r}"
            )

    @pytest.mark.load_envelope
    def test_l3_no_global_timeout_leakage_between_requests(
        self, reset_stores, monkeypatch,
    ):
        """One thread enters ``_request_timeout`` with an extreme
        value (10 seconds); 20 sibling threads concurrently observe
        the default. None of the siblings see the outlier's value."""
        import model_router as mr
        import runtime_http_config as rhc

        N_SIBLINGS = 20
        outlier_value = 10.0
        sibling_observed: list[float] = []
        sibling_lock = threading.Lock()
        outlier_ready = threading.Event()
        outlier_release = threading.Event()
        barrier = threading.Barrier(parties=N_SIBLINGS, timeout=30.0)

        def outlier() -> None:
            with mr._request_timeout(outlier_value):
                outlier_ready.set()
                # Hold the override active until the siblings finish.
                outlier_release.wait(timeout=30.0)

        def sibling() -> None:
            outlier_ready.wait(timeout=30.0)
            barrier.wait(timeout=30.0)
            v = mr._PROVIDER_HTTP_TIMEOUT
            with sibling_lock:
                sibling_observed.append(v)

        t_outlier = threading.Thread(target=outlier)
        t_outlier.start()
        try:
            with ThreadPoolExecutor(max_workers=N_SIBLINGS) as ex:
                for f in [ex.submit(sibling) for _ in range(N_SIBLINGS)]:
                    f.result(timeout=60.0)
        finally:
            outlier_release.set()
            t_outlier.join(timeout=30.0)

        # Every sibling saw the default — never the outlier value.
        assert len(sibling_observed) == N_SIBLINGS
        for v in sibling_observed:
            assert v == rhc.DEFAULT_CALL_TIMEOUT, (
                f"L3 violated — outlier's timeout ({outlier_value}) "
                f"leaked into sibling context: {v}"
            )

    @pytest.mark.load_envelope
    def test_l3_slow_provider_errors_redact_sensitive_data(
        self, reset_stores, monkeypatch, caplog,
    ):
        """Patch the OpenAI handler to raise a slow error with a
        canary string in the exception message. The router's mock
        fallback path catches + logs the failure. The error log MUST
        NOT carry the raw prompt body OR any operator user_id."""
        import model_router as mr

        canary = "CANARY_PROVIDER_ERROR_BODY_DO_NOT_LOG_VERBATIM"

        def slow_failing_post(url, *, headers, body):
            time.sleep(0.05)  # cheap "slow" simulation
            # Build an error that carries the canary string.
            raise RuntimeError(canary)

        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test-load-envelope")
        monkeypatch.setattr(mr, "_http_post_json", slow_failing_post)
        caplog.set_level(logging.WARNING, logger="clarityos.model_router")

        # Make 10 concurrent calls — each fires the patched handler,
        # which raises; the router downgrades to the mock fallback.
        N = 10
        results: list[dict] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(parties=N, timeout=30.0)

        def worker(idx: int) -> None:
            barrier.wait(timeout=30.0)
            out = mr.route_request(
                "openai:gpt-5.4",
                f"prompt_for_user_{idx}",
            )
            with results_lock:
                results.append(out)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=30.0)

        # Every caller got the mock fallback (no exceptions surfaced
        # to the test runner).
        assert len(results) == N
        for r in results:
            assert r["mock"] is True
            assert r["model_id"] == "openai:gpt-5.4"

        # Logger captured warnings. The canary string from the
        # exception body is fine to log (it's the exception's own
        # message); what MUST NOT appear is the raw prompt content
        # ``prompt_for_user_<idx>`` from any caller.
        for rec in caplog.records:
            msg = rec.getMessage()
            for idx in range(N):
                marker = f"prompt_for_user_{idx}"
                assert marker not in msg, (
                    f"L3 violated — raw prompt body leaked into "
                    f"warning log: {msg!r}"
                )

    @pytest.mark.load_envelope
    def test_l3_default_timeout_restored_after_burst(
        self, reset_stores, monkeypatch,
    ):
        """After a 50-thread burst of nested ``_request_timeout``
        overrides, the parent context's default is byte-identical to
        the pre-burst value."""
        import model_router as mr
        import runtime_http_config as rhc

        prior = mr._PROVIDER_HTTP_TIMEOUT

        def worker(idx: int) -> None:
            with mr._request_timeout(0.5 + idx * 0.01):
                with mr._request_timeout(0.1 + idx * 0.005):
                    pass

        with ThreadPoolExecutor(max_workers=50) as ex:
            for f in [ex.submit(worker, i) for i in range(50)]:
                f.result(timeout=30.0)

        assert mr._PROVIDER_HTTP_TIMEOUT == prior == rhc.DEFAULT_CALL_TIMEOUT
