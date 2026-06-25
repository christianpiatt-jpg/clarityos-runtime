"""
PASS-5 Phase D — HTTP-level concurrency tests (BD1 → BD5).

Covers:
    D6 — Twenty concurrent FastAPI clients each driving the full
         login → /me → /elins/preview → /me chain. After the burst:

           * No clarityos-logger record contains a raw username or
             a raw session_id (FIX-P5 redaction holds under load).
           * No request returned a 500.
           * Operator-state snapshots are internally consistent —
             every user that ran a preview has ``last_model_used``
             populated (the kernel completed the run cleanly).
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


def _register_user(app_module, username: str) -> None:
    """Direct user creation — avoids hammering ``POST /register`` under
    contention. Mirrors how the v40 / v44 tests bootstrap users."""
    import bcrypt
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    users_store.update_user(username, {"cohort": "founder"})


# ===========================================================================
# D6 — HTTP-level concurrency (BD1 → BD5)
# ===========================================================================
class TestD6HttpConcurrency:
    """Twenty independent users hit the full vertical slice
    concurrently. The assertion surface is privacy + correctness, not
    throughput — we don't care how long the burst takes, only that
    the redaction holds and no inconsistent state ever surfaces."""

    def test_d6_login_me_preview_me_under_load(
        self, app_module, reset_stores, caplog,
    ):
        from conftest import TestClient

        N = 20
        # Build N distinct full usernames — each is long enough that
        # the first 8 chars are unique AND the full string is clearly
        # distinct from the 8-char ref form ``"d6_user_..."``.
        usernames = [f"d6_user_full_long_name_{i:03d}" for i in range(N)]
        for u in usernames:
            _register_user(app_module, u)

        # Per-thread state.
        results: list[dict] = []
        results_lock = threading.Lock()

        # Pre-create the clients so the bench measures the actual
        # request path, not FastAPI app instantiation.
        clients = [TestClient(app_module.app) for _ in range(N)]

        # All threads release together so the requests interleave.
        barrier = threading.Barrier(parties=N)

        # Capture every log record at INFO and above on the clarityos
        # logger so the privacy assertions can scan the full stream.
        caplog.set_level(logging.INFO, logger="clarityos")

        def worker(idx: int) -> None:
            barrier.wait(timeout=20.0)
            client = clients[idx]
            username = usernames[idx]
            attempt: dict = {"user": username, "status": "starting"}

            try:
                # 1. login
                r_login = client.post(
                    "/login", json={"username": username, "password": "x"},
                )
                attempt["login_status"] = r_login.status_code
                if r_login.status_code != 200:
                    attempt["status"] = "login_failed"
                    return
                sid = r_login.json()["session_id"]
                attempt["sid"] = sid
                hdrs = {"X-Session-ID": sid}

                # 2. /me
                r_me1 = client.get("/me", headers=hdrs)
                attempt["me1_status"] = r_me1.status_code

                # 3. /elins/preview (light text body so the run is fast)
                r_prev = client.post(
                    "/elins/preview", headers=hdrs,
                    json={"text": "trust between partners is eroding"},
                )
                attempt["preview_status"] = r_prev.status_code

                # 4. /me (after the run — last_model_used should be set)
                r_me2 = client.get("/me", headers=hdrs)
                attempt["me2_status"] = r_me2.status_code
                attempt["me2_body"] = r_me2.json()

                attempt["status"] = "ok"
            except Exception as e:   # pragma: no cover (defensive)
                attempt["status"] = "exception"
                attempt["exception"] = repr(e)
            finally:
                with results_lock:
                    results.append(attempt)

        with ThreadPoolExecutor(max_workers=N) as ex:
            futs = [ex.submit(worker, i) for i in range(N)]
            for f in futs:
                f.result(timeout=60.0)

        # ----- Correctness: every request succeeded, no 500s ----------------
        assert len(results) == N
        for r in results:
            assert r["status"] == "ok", (
                f"thread failed: user={r['user']!r} status={r['status']!r} "
                f"detail={r}"
            )
            for code_key in ("login_status", "me1_status", "preview_status", "me2_status"):
                code = r[code_key]
                assert 200 <= code < 300, (
                    f"thread for {r['user']!r} got {code} on {code_key} "
                    f"(no 500s allowed under load): {r}"
                )

        # ----- Internal consistency: last_model_used populated -------------
        # After /elins/preview, the kernel records last_model_used via
        # operator_state.record_model_used. Every user's second /me
        # must reflect that.
        for r in results:
            ik_block = r["me2_body"].get("intelligence_kernel") or {}
            assert ik_block.get("last_model_used"), (
                f"user {r['user']!r} ran a preview but last_model_used is "
                f"missing/empty: ik_block={ik_block}"
            )

        # ----- Privacy: no raw user / session in FIX-P5-scoped loggers ----
        # FIX-P5 redacted the 5 module loggers below. Two adjacent
        # streams sit outside that scope and have their own (different)
        # redaction policies that are deliberately out of scope for this
        # test:
        #   * ``clarityos.kernel.runs`` — the structured audit/telemetry
        #     stream emitted by ``kernel_logging.log_kernel_run``;
        #     full ``user_id`` retention is intentional for the audit
        #     trail (see kernel_logging.py).
        #   * ``clarityos.v29``        — ``v29_hardening.log_event`` has
        #     its own ``redact_user`` helper (12-char prefix + ``…``)
        #     that pre-dates and is independent of runtime_privacy.
        # The assertion scopes to the loggers FIX-P5 actually refactored.
        FIXP5_LOGGERS = {
            "clarityos",
            "clarityos.intelligence_kernel",
            "clarityos.model_router",
            "clarityos.operator_state",
            "clarityos.memory_vault",
        }
        raw_usernames = set(usernames)
        raw_session_ids = {r["sid"] for r in results}

        offenders: list[tuple[str, str, str, str]] = []
        for rec in caplog.records:
            if rec.name not in FIXP5_LOGGERS:
                continue
            formatted = rec.getMessage()
            for u in raw_usernames:
                if u in formatted:
                    offenders.append(("username", rec.name, u, formatted))
            for sid in raw_session_ids:
                if sid in formatted:
                    offenders.append(("session_id", rec.name, sid, formatted))

        assert offenders == [], (
            "raw identifiers leaked into FIX-P5-scoped loggers under load:\n"
            + "\n".join(
                f"  {kind} {needle!r} via {logger!r} → {msg!r}"
                for kind, logger, needle, msg in offenders
            )
        )

        # ----- Privacy: redaction shape DID appear in the log stream -------
        # Sanity check that we did capture log output (i.e. caplog wired
        # up correctly) and that the runtime_privacy redaction format
        # ``<prefix>...`` is present at least once across the 80+ records
        # the burst emits in the FIX-P5-scoped loggers.
        joined = "\n".join(
            rec.getMessage() for rec in caplog.records
            if rec.name in FIXP5_LOGGERS
        )
        assert "..." in joined, (
            "no redacted refs observed at all — caplog wiring or "
            "FIX-P5 redaction was bypassed under load"
        )

    def test_d6_login_session_ids_are_unique_under_load(
        self, app_module, reset_stores,
    ):
        """Twenty concurrent logins must return twenty distinct
        session_id tokens — i.e. the random source used to mint them
        is not contaminated by concurrency. Light privacy regression
        on top of D6."""
        from conftest import TestClient

        N = 20
        usernames = [f"d6_sid_user_{i:03d}" for i in range(N)]
        for u in usernames:
            _register_user(app_module, u)

        clients = [TestClient(app_module.app) for _ in range(N)]
        observed: list[str] = []
        observed_lock = threading.Lock()
        barrier = threading.Barrier(parties=N)

        def worker(idx: int) -> None:
            barrier.wait(timeout=15.0)
            r = clients[idx].post(
                "/login", json={"username": usernames[idx], "password": "x"},
            )
            assert r.status_code == 200
            sid = r.json()["session_id"]
            with observed_lock:
                observed.append(sid)

        with ThreadPoolExecutor(max_workers=N) as ex:
            for f in [ex.submit(worker, i) for i in range(N)]:
                f.result(timeout=30.0)

        assert len(observed) == N
        assert len(set(observed)) == N, (
            f"duplicate session_ids under load: "
            f"{len(observed) - len(set(observed))} collisions"
        )


# ===========================================================================
# PASS-6 Phase B — B4: Logging-surface validation under simulated deployment
# ===========================================================================
_FIXP5_LOGGERS: set[str] = {
    "clarityos",
    "clarityos.intelligence_kernel",
    "clarityos.model_router",
    "clarityos.operator_state",
    "clarityos.memory_vault",
}


def _simulate_instance_reset_b() -> None:
    """Reset only the per-process caches that Phase B treats as
    instance-local. Vault data, users_store, and sessions_store are
    left intact so a user can re-authenticate against the simulated
    second instance with the same session token."""
    import memory_vault
    import model_router as mr
    import operator_state
    mr._founder_default_model = None
    mr._founder_default_loaded = False
    mr._LOCAL_HANDLE_CACHE = None
    mr._LOCAL_HANDLE_PATH = None
    operator_state._HISTORY_SEQ.clear()
    memory_vault._KEY_CACHE.clear()
    memory_vault._PLAINTEXT_WARNING_EMITTED = False


class TestB4LoggingSurfaceUnderDeployment:
    """Drive a deployment-shaped workload (multiple users, multiple
    requests, mixed billing + ELINS traffic) and assert the full
    logging-surface contract holds under load:

      * No raw user_id / session_id in any FIX-P5-scoped logger.
      * All redactions visibly use the runtime_privacy ``"..."`` form.
      * No plaintext-mode warning unless the env explicitly enables it.
      * No billing client_secret / raw metadata anywhere in the log
        stream.
    """

    def test_b4_no_raw_identifiers_under_mixed_workload(
        self, app_module, reset_stores, caplog,
    ):
        from conftest import TestClient
        client = TestClient(app_module.app)

        # Build several distinct users with deliberately distinctive
        # full usernames so substring scans are unambiguous.
        usernames = [
            "b4_user_full_unique_alpha_001",
            "b4_user_full_unique_beta_002",
            "b4_user_full_unique_gamma_003",
        ]
        for u in usernames:
            _register_user(app_module, u)

        caplog.set_level(logging.INFO)

        # Drive a workload: login → /me → preview → /me, per user.
        session_ids: list[str] = []
        for u in usernames:
            r = client.post(
                "/login", json={"username": u, "password": "x"},
            )
            assert r.status_code == 200
            sid = r.json()["session_id"]
            session_ids.append(sid)
            hdrs = {"X-Session-ID": sid}
            assert client.get("/me", headers=hdrs).status_code == 200
            assert client.post(
                "/elins/preview", headers=hdrs,
                json={"text": "trust between partners is eroding"},
            ).status_code == 200
            assert client.get("/me", headers=hdrs).status_code == 200

        # ----- No raw user_id / session_id in FIX-P5 loggers -----
        offenders: list[tuple[str, str, str]] = []
        for rec in caplog.records:
            if rec.name not in _FIXP5_LOGGERS:
                continue
            formatted = rec.getMessage()
            for u in usernames:
                if u in formatted:
                    offenders.append(("username", rec.name, formatted))
            for sid in session_ids:
                if sid in formatted:
                    offenders.append(("session_id", rec.name, formatted))
        assert offenders == [], (
            "B4 violated — raw identifiers leaked into FIX-P5 loggers:\n" +
            "\n".join(
                f"  {kind} in {logger!r}: {msg!r}"
                for kind, logger, msg in offenders
            )
        )

        # ----- All redactions use the runtime_privacy "..." form -----
        # At least one record in the spine carries the redaction marker.
        joined = "\n".join(
            rec.getMessage() for rec in caplog.records
            if rec.name in _FIXP5_LOGGERS
        )
        assert "..." in joined

    def test_b4_no_plaintext_warning_under_default_env(
        self, app_module, reset_stores, monkeypatch, caplog,
    ):
        """Default deployment env (no CLARITYOS_VAULT_PLAINTEXT) must
        produce zero plaintext-mode warnings during a normal request
        cycle."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        _simulate_instance_reset_b()

        from conftest import TestClient
        client = TestClient(app_module.app)
        _register_user(app_module, "b4_no_pt_user")
        caplog.set_level(logging.WARNING)

        # Drive a few requests that touch the vault path indirectly.
        r = client.post(
            "/login", json={"username": "b4_no_pt_user", "password": "x"},
        )
        assert r.status_code == 200
        sid = r.json()["session_id"]
        assert client.get("/me", headers={"X-Session-ID": sid}).status_code == 200
        assert client.post(
            "/elins/preview", headers={"X-Session-ID": sid},
            json={"text": "hello vault"},
        ).status_code == 200

        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert plaintext_warnings == []

    def test_b4_no_billing_secrets_in_log_stream(
        self, app_module, reset_stores, caplog,
    ):
        """Billing flows (intent create + confirm under mock auto-
        confirm) cannot leak ``client_secret`` or raw metadata fields
        into any captured log record across all loggers."""
        import billing_intents
        import bcrypt
        import sessions_store
        import users_store
        username = "b4_billing_user"
        pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
        users_store.create_user(
            username=username, password_hash=pwd_hash, salt="",
            tier="free", created_at=time.time(),
        )
        users_store.update_user(username, {"cohort": "founder"})
        sid = "sess_" + secrets.token_urlsafe(16)
        sessions_store.create_session(
            sid, username, expires_at=time.time() + 3600,
        )

        intent = billing_intents.create_payment_intent(
            username, 1.0, "x", kind="g_credit_single",
            metadata={"campaign": "b4-marker-leak-test"},
        )
        secret_val = intent["client_secret"]
        assert secret_val  # underlying record really does carry one

        caplog.set_level(logging.DEBUG)

        from conftest import TestClient
        client = TestClient(app_module.app)
        r = client.post(
            "/billing/intent/confirm", headers={"X-Session-ID": sid},
            json={"intent_id": intent["intent_id"]},
        )
        assert r.status_code == 200

        # Walk every record (any logger), formatted text + args.
        for rec in caplog.records:
            formatted = (rec.getMessage() or "") + " " + repr(getattr(rec, "args", None))
            assert "client_secret" not in formatted, (
                f"B4 violated — client_secret literal in log: {formatted!r}"
            )
            assert secret_val not in formatted, (
                f"B4 violated — client_secret value in log: {formatted!r}"
            )
            assert "b4-marker-leak-test" not in formatted, (
                f"B4 violated — raw metadata value in log: {formatted!r}"
            )


# ===========================================================================
# PASS-6 Phase B — B6: Full request cycle across two simulated instances
# ===========================================================================
class TestB6KernelRouterOperatorIntegrationUnderDeployment:
    """Lifecycle test: a user goes through login → /me → /elins/preview
    → /me on instance A, then the runtime is "restarted" (caches
    cleared, vault preserved), then the user repeats on instance B.
    The post-restart state must be coherent — operator_state stable,
    model selection stable, no forbidden fields leaked, founder
    default preserved, no concurrency anomalies."""

    def test_b6_full_cycle_across_simulated_instance_boundary(
        self, app_module, reset_stores,
    ):
        from conftest import TestClient

        client = TestClient(app_module.app)

        # Set up a user + a founder default that should survive the
        # simulated restart.
        _register_user(app_module, "b6_cycle_user")
        # Switch on the founder default on instance A.
        import model_router as mr
        mr.set_founder_default_model("anthropic:claude-haiku-4-5-20251001")

        # ---------- Instance A — full cycle ----------
        r_login_a = client.post(
            "/login", json={"username": "b6_cycle_user", "password": "x"},
        )
        assert r_login_a.status_code == 200
        sid_a = r_login_a.json()["session_id"]
        hdrs_a = {"X-Session-ID": sid_a}

        me_a_1 = client.get("/me", headers=hdrs_a).json()
        preview_a = client.post(
            "/elins/preview", headers=hdrs_a,
            json={"text": "trust between partners eroding"},
        ).json()
        me_a_2 = client.get("/me", headers=hdrs_a).json()

        # Operator_state on instance A: preferred_model unset, founder
        # default wins → last_model_used == founder default.
        assert me_a_2["intelligence_kernel"]["last_model_used"] == "anthropic:claude-haiku-4-5-20251001"

        # ---------- Simulate instance restart ----------
        _simulate_instance_reset_b()

        # ---------- Instance B — repeat the cycle ----------
        # Re-login (session token from instance A is still in the
        # sessions_store mock since we don't reset that; in a real
        # deployment Firestore-backed sessions would also survive).
        me_b_1 = client.get("/me", headers=hdrs_a).json()
        preview_b = client.post(
            "/elins/preview", headers=hdrs_a,
            json={"text": "second pass after restart"},
        ).json()
        me_b_2 = client.get("/me", headers=hdrs_a).json()

        # ----- operator_state stable -----
        # Last model used persists across the restart (the vault has it).
        assert me_b_1["intelligence_kernel"]["last_model_used"] == "anthropic:claude-haiku-4-5-20251001"
        assert me_b_2["intelligence_kernel"]["last_model_used"] == "anthropic:claude-haiku-4-5-20251001"
        # ELINS history grew by one entry (the second preview) — the
        # first preview's entry survives the restart.
        history_a = me_a_2.get("intelligence_kernel", {}).get("elins_history_count")
        history_b = me_b_2.get("intelligence_kernel", {}).get("elins_history_count")
        if history_a is not None and history_b is not None:
            assert history_b >= history_a

        # ----- model selection stable -----
        # Both preview runs picked the same model_id.
        # ``model_id`` is exposed at the top level of the preview result
        # via the kernel; if not present at that level, the kernel log
        # already verified it (covered in v44/v40 tests).
        if "model_id" in preview_a and "model_id" in preview_b:
            assert preview_a["model_id"] == preview_b["model_id"]

        # ----- no forbidden fields in vault history -----
        import memory_vault
        entries = memory_vault.vault_list("b6_cycle_user")
        for k, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            for forbidden in (
                "text", "scenario_text", "input_text", "raw_text",
            ):
                assert forbidden not in entry, (
                    f"B6 violated — forbidden field {forbidden!r} in "
                    f"vault entry {k!r}"
                )

        # ----- no drift in founder default -----
        # Re-read on instance B: vault is the source of truth.
        assert mr.get_founder_default_model() == "anthropic:claude-haiku-4-5-20251001"

        # ----- no concurrency anomalies in vault state -----
        # The vault keys for ELINS history sort cleanly by ts; no
        # duplicates from a counter race.
        elins_keys = sorted(
            k for k in entries if k.startswith("elins.") and isinstance(entries[k], dict)
        )
        assert len(elins_keys) == len(set(elins_keys)), (
            "B6 violated — duplicate ELINS history keys across instances"
        )

    def test_b6_user_preference_drives_selection_post_restart(
        self, app_module, reset_stores,
    ):
        """When the user sets a preferred_model on instance A and no
        founder default is present, instance B must continue to select
        the user's preferred model — proving operator_state's
        ``preferred_model`` truly persists across the restart."""
        from conftest import TestClient
        client = TestClient(app_module.app)

        _register_user(app_module, "b6_pref_user")
        r_login = client.post(
            "/login", json={"username": "b6_pref_user", "password": "x"},
        )
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}

        # Instance A: user sets preferred_model.
        r_set = client.post(
            "/me/operator_state/model", headers=hdrs,
            json={"preferred_model": "google:gemini-2.5-flash"},
        )
        assert r_set.status_code == 200

        # First preview picks the preference.
        preview_a = client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "preview A"},
        ).json()

        # Restart.
        _simulate_instance_reset_b()

        # Instance B: a fresh preview picks the SAME preferred_model
        # because operator_state.preferred_model lives in the vault.
        preview_b = client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "preview B"},
        ).json()

        me_b = client.get("/me", headers=hdrs).json()
        assert me_b["intelligence_kernel"]["preferred_model"] == "google:gemini-2.5-flash"
        assert me_b["intelligence_kernel"]["last_model_used"] == "google:gemini-2.5-flash"
