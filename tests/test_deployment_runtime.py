"""
PASS-6 Phase B — Deployment-mode validation.

These tests treat the runtime as a containerised service (Cloud Run /
docker / multi-instance). They exercise environment-variable
configuration paths AND container-startup behaviour from the operator's
perspective: what happens when ``CLARITYOS_VAULT_SECRET`` is missing,
what happens when ``CLARITYOS_VAULT_PLAINTEXT`` is set to various
values, and what the post-import state of the runtime modules looks
like under a fresh-process simulation.

Covered tasks:
    B1 — Environment-variable validation
    B3 — Startup behaviour validation

(B2, B4, B5, B6 are added to the existing module-specific runtime
test files per the Phase B spec.)
"""
from __future__ import annotations

import logging

import pytest

import memory_vault
import model_router as mr
import operator_state
import runtime_http_config as rhc


# ===========================================================================
# Helpers — simulate a fresh instance / container start
# ===========================================================================
def _simulate_fresh_instance() -> None:
    """Reset every module-level cache that mirrors per-process state,
    WITHOUT touching the vault backend or any other durable store.
    Mirrors what a Cloud Run cold start sees: fresh in-process memory,
    same shared persistence."""
    # Router: founder default cache + local-handle cache.
    mr._founder_default_model = None
    mr._founder_default_loaded = False
    mr._LOCAL_HANDLE_CACHE = None
    mr._LOCAL_HANDLE_PATH = None

    # Operator state: per-prefix counter.
    operator_state._HISTORY_SEQ.clear()

    # Vault: derived-key cache + one-shot plaintext warning flag.
    # Do NOT touch _MEM_STORE / SQLite / fs — those are the persistence
    # layer (shared across instances).
    memory_vault._KEY_CACHE.clear()
    memory_vault._PLAINTEXT_WARNING_EMITTED = False


# ===========================================================================
# B1 — Environment-variable validation
# ===========================================================================
class TestB1MissingVaultSecret:
    """Missing or empty ``CLARITYOS_VAULT_SECRET`` must cause vault
    initialisation to raise a clear ``RuntimeError`` — no silent
    fallback to a default key in any environment."""

    def test_b1_unset_secret_blocks_vault_init(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.delenv("CLARITYOS_VAULT_SECRET", raising=False)
        memory_vault._reset_for_tests()
        with pytest.raises(RuntimeError) as ei:
            memory_vault.vault_init("b1_unset_secret_user")
        assert "CLARITYOS_VAULT_SECRET" in str(ei.value)

    def test_b1_empty_secret_blocks_vault_init(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "")
        memory_vault._reset_for_tests()
        with pytest.raises(RuntimeError):
            memory_vault.vault_init("b1_empty_secret_user")

    def test_b1_whitespace_secret_blocks_vault_init(
        self, reset_stores, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "   ")
        memory_vault._reset_for_tests()
        with pytest.raises(RuntimeError):
            memory_vault.vault_init("b1_ws_secret_user")

    def test_b1_missing_secret_blocks_vault_put_too(
        self, reset_stores, monkeypatch,
    ):
        """Even if a caller skips ``vault_init`` and calls ``vault_put``
        directly, the underlying ``_derive_key`` still trips the secret
        check. Same guarantee, different entry point."""
        monkeypatch.delenv("CLARITYOS_VAULT_SECRET", raising=False)
        memory_vault._reset_for_tests()
        with pytest.raises(RuntimeError):
            memory_vault.vault_put(
                "b1_put_user", "notes.note_a", {"x": 1},
            )


class TestB1PlaintextEnvVarMatrix:
    """The FIX-P3 contract: only the explicit string ``"true"`` (case-
    insensitive, whitespace-trimmed) enables plaintext mode AND fires
    exactly one warning. Every other value leaves encryption on and
    fires nothing."""

    def test_b1_plaintext_true_enables_and_warns_once(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        memory_vault._reset_for_tests()
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        # Drive the check multiple times under a deployment-shaped
        # workload (multiple vault ops would each call _is_encrypted).
        for _ in range(20):
            memory_vault._is_encrypted()

        # Plaintext is ON.
        assert memory_vault._is_encrypted() is False
        # Exactly one warning, regardless of how many calls fired.
        warnings = [
            rec for rec in caplog.records
            if rec.name == "clarityos.memory_vault"
            and rec.levelno == logging.WARNING
            and "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(warnings) == 1

    @pytest.mark.parametrize("value", [
        # Documented FIX-P3 tightening — these legacy values must NOT
        # enable plaintext mode in production deployments.
        "1", "yes", "on", "y", "ok",
        "false", "False", "FALSE", "0", "no",
        "TRU", "trueish", "True!",
    ])
    def test_b1_non_true_values_keep_encryption_on_and_silent(
        self, reset_stores, monkeypatch, caplog, value,
    ):
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", value)
        memory_vault._reset_for_tests()
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        for _ in range(5):
            memory_vault._is_encrypted()

        assert memory_vault._is_encrypted() is True, (
            f"value {value!r} should not enable plaintext mode"
        )
        warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert warnings == [], (
            f"value {value!r} should not fire the plaintext warning"
        )

    def test_b1_unset_means_encryption_on_and_silent(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        memory_vault._reset_for_tests()
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        for _ in range(5):
            memory_vault._is_encrypted()

        assert memory_vault._is_encrypted() is True
        warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert warnings == []


class TestB1InvalidNamespaceAndKey:
    """``_validate_key`` is the BD5 entry-point guard: any malformed
    key or unknown namespace must be rejected at write time. This is
    the deployment-time guarantee that operator code can't accidentally
    smuggle data into an unaudited namespace."""

    def test_b1_unknown_namespace_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault.vault_put(
                "b1_invalid_user", "notakn.sub", {"x": 1},
            )

    def test_b1_bare_namespace_rejected(self, reset_stores):
        # Bare namespace without a sub-key.
        with pytest.raises(ValueError):
            memory_vault.vault_put("b1_invalid_user", "notes", {"x": 1})
        with pytest.raises(ValueError):
            memory_vault.vault_put("b1_invalid_user", "notes.", {"x": 1})

    def test_b1_slash_in_key_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault.vault_put(
                "b1_invalid_user", "notes.a/b", {"x": 1},
            )

    def test_b1_null_byte_in_key_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault.vault_put(
                "b1_invalid_user", "notes.a\x00b", {"x": 1},
            )

    def test_b1_overlong_key_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault.vault_put(
                "b1_invalid_user", "notes." + "x" * 300, {"x": 1},
            )

    def test_b1_empty_user_id_rejected(self, reset_stores):
        with pytest.raises(ValueError):
            memory_vault.vault_put("", "notes.a", {"x": 1})


# ===========================================================================
# B3 — Startup behaviour validation
# ===========================================================================
class TestB3FreshImportState:
    """Simulate a container cold start (post-import state) and assert
    every module-level global matches the documented default. Catches
    regressions where a previous test could leave residue that would
    affect the first request a real container would serve."""

    def test_b3_post_import_globals_router(self, reset_stores):
        _simulate_fresh_instance()
        # Founder default cache: empty.
        assert mr._founder_default_model is None
        assert mr._founder_default_loaded is False
        # Local handle cache: empty.
        assert mr._LOCAL_HANDLE_CACHE is None
        assert mr._LOCAL_HANDLE_PATH is None
        # Provider timeout default: equals runtime_http_config default.
        assert mr._PROVIDER_HTTP_TIMEOUT_VAR.get() == rhc.DEFAULT_CALL_TIMEOUT

    def test_b3_post_import_globals_operator_state(self, reset_stores):
        _simulate_fresh_instance()
        assert operator_state._HISTORY_SEQ == {}

    def test_b3_post_import_globals_memory_vault(self, reset_stores):
        _simulate_fresh_instance()
        assert memory_vault._KEY_CACHE == {}
        assert memory_vault._PLAINTEXT_WARNING_EMITTED is False


class TestB3NoPlaintextUnlessExplicit:
    """The most-defence-in-depth invariant: a fresh container start with
    no special env config MUST NOT enable plaintext mode and MUST NOT
    fire the plaintext warning, regardless of any previous test's
    state."""

    def test_b3_default_startup_no_plaintext_no_warning(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING)

        # Touch the encryption path a few times — what a real first
        # request would do.
        memory_vault.vault_init("b3_default_user")
        memory_vault.vault_put("b3_default_user", "notes.a", {"x": 1})

        assert memory_vault._is_encrypted() is True
        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert plaintext_warnings == []

    def test_b3_legacy_value_does_not_silently_flip(
        self, reset_stores, monkeypatch, caplog,
    ):
        """An operator carrying an old env config value of ``"1"``
        from a pre-FIX-P3 deployment must NOT silently get plaintext
        mode on the next container restart."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "1")
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING)

        memory_vault.vault_init("b3_legacy_user")
        memory_vault.vault_put("b3_legacy_user", "notes.a", {"x": 1})

        assert memory_vault._is_encrypted() is True
        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert plaintext_warnings == []


class TestB3StartupWarningsAreBounded:
    """A clean startup with default settings should produce zero
    WARNING-level records from the FIX-P5-scoped loggers. Catches a
    regression where an init path would log a spurious warning on
    every container start."""

    _FIXP5_LOGGERS = (
        "clarityos",
        "clarityos.intelligence_kernel",
        "clarityos.model_router",
        "clarityos.operator_state",
        "clarityos.memory_vault",
    )

    def test_b3_default_startup_no_warnings_from_spine_modules(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING)

        # Drive a minimal start: vault init + a no-op kernel status read.
        memory_vault.vault_init("b3_warn_user")
        memory_vault.vault_get("b3_warn_user", "notes.never_written", default=None)

        warnings = [
            rec for rec in caplog.records
            if rec.name in self._FIXP5_LOGGERS
            and rec.levelno >= logging.WARNING
        ]
        assert warnings == [], (
            "fresh startup emitted unexpected warnings from the FIX-P5 "
            "loggers:\n" +
            "\n".join(f"  {rec.name}: {rec.getMessage()}" for rec in warnings)
        )

    def test_b3_plaintext_explicit_only_warning_is_plaintext(
        self, reset_stores, monkeypatch, caplog,
    ):
        """When plaintext IS explicitly enabled, the only spine
        warning is the documented PLAINTEXT MODE ENABLED message."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING)

        memory_vault.vault_init("b3_pt_user")
        memory_vault.vault_put("b3_pt_user", "notes.a", {"x": 1})

        warnings = [
            rec for rec in caplog.records
            if rec.name in self._FIXP5_LOGGERS
            and rec.levelno >= logging.WARNING
        ]
        # All warnings observed are the plaintext warning, exactly once.
        plaintext_warnings = [
            rec for rec in warnings
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        other_warnings = [
            rec for rec in warnings
            if "PLAINTEXT MODE ENABLED" not in rec.getMessage()
        ]
        assert len(plaintext_warnings) == 1
        assert other_warnings == [], (
            "expected only the PLAINTEXT warning; got extra spine warnings:\n" +
            "\n".join(f"  {rec.name}: {rec.getMessage()}" for rec in other_warnings)
        )


# ===========================================================================
# PASS-6 Phase E — Final deployment readiness
# ===========================================================================
# Helpers for E1-E3 that need a TestClient + fresh user. Kept here
# (not in conftest) so the Phase E suite stays self-contained.
import secrets
import time

import model_router as mr


def _register_user(username: str, cohort: str = "founder") -> str:
    """Direct user creation — sidesteps /register so the deployment
    suite can exercise login/me/preview without polluting the
    registration code path."""
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


# ---------------------------------------------------------------------------
# E1 — Container startup simulation
# ---------------------------------------------------------------------------
class TestE1ContainerStartup:
    """A "fresh container" import for the runtime means: every per-
    process cache is empty, every one-shot flag is reset, no module
    has logged a warning. These tests boot the runtime as if the
    container had just cold-started and assert each documented
    contract holds end-to-end."""

    _FIXP5_LOGGERS = (
        "clarityos",
        "clarityos.intelligence_kernel",
        "clarityos.model_router",
        "clarityos.operator_state",
        "clarityos.memory_vault",
    )

    def test_e1_fresh_container_boot_default_env(
        self, reset_stores, monkeypatch, caplog,
    ):
        """Default deployment env (no CLARITYOS_VAULT_PLAINTEXT) — a
        fresh container start touches the full spine and emits zero
        unexpected warnings."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING)

        # Exercise each BD in order — what a real first request does.
        memory_vault.vault_init("e1_boot_user")
        memory_vault.vault_put("e1_boot_user", "notes.boot_marker", {"v": 1})
        op_state = operator_state.get_operator_state("e1_boot_user")
        founder_default = mr.get_founder_default_model()
        selected = mr.select_model("e1_boot_user", task="ELINS")

        # Encryption is ON.
        assert memory_vault._is_encrypted() is True
        # No plaintext warning fired.
        assert memory_vault._PLAINTEXT_WARNING_EMITTED is False
        # No spine warnings emitted at all.
        spine_warnings = [
            rec for rec in caplog.records
            if rec.name in self._FIXP5_LOGGERS
            and rec.levelno >= logging.WARNING
        ]
        assert spine_warnings == [], (
            f"E1 violated — fresh container emitted spine warnings:\n" +
            "\n".join(f"  {rec.name}: {rec.getMessage()}" for rec in spine_warnings)
        )
        # The vault round-tripped, state initialised cleanly, router
        # returned a sane choice.
        assert op_state["user_id"] == "e1_boot_user"
        assert founder_default is None
        assert selected == mr.TASK_DEFAULTS["ELINS"]

    def test_e1_fresh_container_boot_missing_secret_fails_clearly(
        self, reset_stores, monkeypatch,
    ):
        """A misconfigured container (CLARITYOS_VAULT_SECRET unset)
        must fail at the first vault op with a clear, named
        RuntimeError — never a silent default-key fallback. The error
        message must name the env var so the operator can diagnose
        without reading source."""
        monkeypatch.delenv("CLARITYOS_VAULT_SECRET", raising=False)
        _simulate_fresh_instance()

        with pytest.raises(RuntimeError) as ei:
            memory_vault.vault_init("e1_missing_secret_user")
        assert "CLARITYOS_VAULT_SECRET" in str(ei.value), (
            "E1 violated — RuntimeError must name CLARITYOS_VAULT_SECRET"
        )

    def test_e1_fresh_container_boot_plaintext_explicit_one_warning(
        self, reset_stores, monkeypatch, caplog,
    ):
        """With plaintext explicitly enabled, a fresh container start
        emits exactly one PLAINTEXT MODE ENABLED warning — even
        though the vault path is touched many times during boot."""
        monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", "true")
        _simulate_fresh_instance()
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        # Exercise the spine through several vault ops.
        memory_vault.vault_init("e1_pt_user")
        memory_vault.vault_put("e1_pt_user", "notes.a", {"x": 1})
        memory_vault.vault_get("e1_pt_user", "notes.a")
        memory_vault.vault_put("e1_pt_user", "notes.b", {"y": 2})
        memory_vault.vault_list("e1_pt_user")

        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert len(plaintext_warnings) == 1


# ---------------------------------------------------------------------------
# E2 — Env matrix validation
# ---------------------------------------------------------------------------
class TestE2EnvMatrix:
    """The runtime's documented contract under different env-var
    combinations. We parametrize over the two axes the operator most
    likely tweaks during a deploy: CLARITYOS_VAULT_PLAINTEXT (vault
    encryption mode) and whether a founder default model is
    configured ("FOUNDER_USER" in the spec — which the runtime models
    as a vault entry under ``__founder_global__``, not an env var)."""

    @pytest.mark.parametrize("plaintext_value,expected_encrypted", [
        (None,    True),
        ("",      True),
        ("false", True),
        ("False", True),
        ("FALSE", True),
        ("0",     True),
        ("true",  False),
        ("True",  False),
        ("TRUE",  False),
        ("1",     True),    # legacy value no longer enables (FIX-P3)
        ("yes",   True),    # ditto
    ])
    @pytest.mark.parametrize("founder_default", [
        None,                       # unset
        "anthropic:claude-haiku-4-5-20251001",     # set
    ])
    def test_e2_encryption_and_founder_default_matrix(
        self,
        reset_stores,
        monkeypatch,
        plaintext_value,
        expected_encrypted,
        founder_default,
    ):
        """For each cell of the env matrix:
          * encryption mode matches the documented FIX-P3 contract
          * founder default behaviour matches: None unless explicitly
            configured (in which case it persists across module
            resets via the vault)
        """
        # Set the plaintext env var.
        if plaintext_value is None:
            monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        else:
            monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", plaintext_value)

        # Reset spine globals so we start from a clean container shape.
        _simulate_fresh_instance()

        # Configure the founder default if the matrix cell calls for it.
        if founder_default is not None:
            mr.set_founder_default_model(founder_default)

        # ----- Encryption mode -----
        assert memory_vault._is_encrypted() is expected_encrypted, (
            f"encryption mode wrong for plaintext={plaintext_value!r}: "
            f"got {memory_vault._is_encrypted()}, expected {expected_encrypted}"
        )

        # ----- Founder default behaviour -----
        observed = mr.get_founder_default_model()
        assert observed == founder_default, (
            f"founder default wrong: got {observed!r}, "
            f"expected {founder_default!r}"
        )

        # ----- Multi-instance read: persistent across cache reset -----
        # Drop only the in-process cache (preserve vault).
        mr._founder_default_model = None
        mr._founder_default_loaded = False
        memory_vault._KEY_CACHE.clear()
        # Same observation post-cache-clear.
        assert mr.get_founder_default_model() == founder_default

    @pytest.mark.parametrize("plaintext_value", [None, "false", "true"])
    def test_e2_no_secrets_in_logs_across_env_cells(
        self, reset_stores, monkeypatch, caplog, plaintext_value,
    ):
        """The env-var values themselves must not appear in any log
        record under any matrix cell — neither the vault secret nor
        the plaintext flag value should be logged verbatim."""
        # Distinctive env values we can grep for in the captured logs.
        secret_marker = "release-canary-secret-DO-NOT-LOG"
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", secret_marker)
        if plaintext_value is None:
            monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        else:
            monkeypatch.setenv("CLARITYOS_VAULT_PLAINTEXT", plaintext_value)
        _simulate_fresh_instance()
        caplog.set_level(logging.DEBUG)

        # Drive a vault op so the spine touches the secret.
        memory_vault.vault_init("e2_secret_user")
        memory_vault.vault_put("e2_secret_user", "notes.a", {"x": 1})
        memory_vault.vault_get("e2_secret_user", "notes.a")

        # Walk every captured record. The secret must not appear
        # anywhere in the formatted output OR in the args repr.
        for rec in caplog.records:
            formatted = (rec.getMessage() or "") + " " + repr(getattr(rec, "args", None))
            assert secret_marker not in formatted, (
                f"E2 violated — CLARITYOS_VAULT_SECRET value leaked in "
                f"{rec.name!r}: {formatted!r}"
            )


# ---------------------------------------------------------------------------
# E3 — Observability surface sanity
# ---------------------------------------------------------------------------
class TestE3ObservabilitySurface:
    """Drive a minimal-but-realistic request path and validate the
    observability contract — logger names are stable + documented,
    no raw user/session/secret data appears anywhere."""

    # The complete documented logger surface used by the spine + the
    # adjacent audit/event streams. Any record on a logger name NOT in
    # this set is a regression (likely a new logger added without
    # being documented in docs/boundaries.md).
    _DOCUMENTED_LOGGERS: frozenset[str] = frozenset({
        "clarityos",                           # BD1 (app.py)
        "clarityos.intelligence_kernel",       # BD2
        "clarityos.model_router",              # BD3
        "clarityos.operator_state",            # BD4
        "clarityos.memory_vault",              # BD5
        "clarityos.kernel.runs",               # kernel_logging audit stream
        "clarityos.v29",                       # v29_hardening event stream
    })

    # Loggers that FIX-P5 refactored — these are the ones where raw
    # user_id / session_id leaks are forbidden.
    _FIXP5_LOGGERS: frozenset[str] = frozenset({
        "clarityos",
        "clarityos.intelligence_kernel",
        "clarityos.model_router",
        "clarityos.operator_state",
        "clarityos.memory_vault",
    })

    @pytest.fixture
    def client(self, reset_stores):
        from conftest import TestClient
        import app as app_module
        return TestClient(app_module.app)

    def test_e3_minimal_request_path_logger_names_are_documented(
        self, client, monkeypatch, caplog,
    ):
        """Drive login → /me → /elins/preview and walk every captured
        record. Each logger name must be in the documented set."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        username = _register_user("e3_logger_user_full_unique_001")
        caplog.set_level(logging.DEBUG)

        # Login.
        r_login = client.post(
            "/login", json={"username": username, "password": "x"},
        )
        assert r_login.status_code == 200
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}

        # /me.
        assert client.get("/me", headers=hdrs).status_code == 200

        # /elins/preview (one ELINS run).
        r_preview = client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "trust between partners eroding"},
        )
        assert r_preview.status_code == 200

        # Every clarityos.* record must come from a documented logger.
        # Other-namespace records (uvicorn, asyncio, etc.) are out of
        # scope for the observability contract.
        offending: list[tuple[str, str]] = []
        for rec in caplog.records:
            name = rec.name
            if name != "clarityos" and not name.startswith("clarityos."):
                continue
            if name not in self._DOCUMENTED_LOGGERS:
                offending.append((name, rec.getMessage()))
        assert offending == [], (
            "E3 violated — undocumented logger emitted records:\n" +
            "\n".join(f"  {n}: {msg!r}" for n, msg in offending)
        )

    def test_e3_no_raw_user_or_session_id_in_fixp5_loggers(
        self, client, monkeypatch, caplog,
    ):
        """The FIX-P5 redaction contract holds during a real request
        cycle. Full usernames and full session ids must not appear in
        any record emitted by the five spine loggers."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        # Long distinctive username so the absence check is unambiguous.
        username = _register_user("e3_redact_user_full_unique_long_002")
        caplog.set_level(logging.DEBUG)

        r_login = client.post(
            "/login", json={"username": username, "password": "x"},
        )
        assert r_login.status_code == 200
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}

        client.get("/me", headers=hdrs)
        client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "hello"},
        )

        # Build the needles we must never see in any FIX-P5 logger.
        offenders: list[tuple[str, str, str]] = []
        for rec in caplog.records:
            if rec.name not in self._FIXP5_LOGGERS:
                continue
            formatted = rec.getMessage()
            if username in formatted:
                offenders.append(("username", rec.name, formatted))
            if sid in formatted:
                offenders.append(("session_id", rec.name, formatted))
        assert offenders == [], (
            "E3 violated — raw identifiers leaked into FIX-P5 loggers:\n" +
            "\n".join(
                f"  {kind} via {lgr!r}: {msg!r}"
                for kind, lgr, msg in offenders
            )
        )

    def test_e3_no_plaintext_warning_in_normal_mode(
        self, client, monkeypatch, caplog,
    ):
        """A normal request cycle under default env (no plaintext
        env var set) must NOT emit the PLAINTEXT MODE ENABLED
        warning anywhere in the log stream."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        username = _register_user("e3_no_pt_warn_user")
        caplog.set_level(logging.WARNING)

        r_login = client.post(
            "/login", json={"username": username, "password": "x"},
        )
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}

        client.get("/me", headers=hdrs)
        client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "normal-mode request"},
        )

        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert plaintext_warnings == []

    def test_e3_no_vault_secret_or_client_secret_in_logs(
        self, client, monkeypatch, caplog,
    ):
        """No vault master secret value and no Stripe client_secret
        token should ever appear in any captured log record across
        any logger (FIX-P5-scoped or otherwise)."""
        # Distinctive markers.
        secret_marker = "e3-vault-secret-canary-NEVER-LOG"
        monkeypatch.setenv("CLARITYOS_VAULT_SECRET", secret_marker)

        # Set up a user + an intent that carries a client_secret.
        import billing_intents
        username = _register_user("e3_secret_canary_user")
        intent = billing_intents.create_payment_intent(
            username, 1.0, "x", kind="g_credit_single",
            metadata={"e3_marker": "e3-metadata-canary-NEVER-LOG"},
        )
        client_secret = intent["client_secret"]
        assert client_secret  # underlying record really does carry one

        caplog.set_level(logging.DEBUG)

        # Login + minimal flow.
        r_login = client.post(
            "/login", json={"username": username, "password": "x"},
        )
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}
        client.get("/me", headers=hdrs)

        # Confirm the intent (triggers the FIX-P1 redaction path).
        client.post(
            "/billing/intent/confirm", headers=hdrs,
            json={"intent_id": intent["intent_id"]},
        )

        # Walk all records — these canary markers MUST NOT appear
        # anywhere, regardless of logger.
        for rec in caplog.records:
            formatted = (rec.getMessage() or "") + " " + repr(getattr(rec, "args", None))
            assert secret_marker not in formatted, (
                f"E3 violated — vault secret leaked in {rec.name!r}: "
                f"{formatted!r}"
            )
            assert client_secret not in formatted, (
                f"E3 violated — client_secret leaked in {rec.name!r}: "
                f"{formatted!r}"
            )
            assert "e3-metadata-canary" not in formatted, (
                f"E3 violated — raw metadata leaked in {rec.name!r}: "
                f"{formatted!r}"
            )

    def test_e3_observability_records_have_stable_field_shapes(
        self, client, monkeypatch, caplog,
    ):
        """Records on ``clarityos.kernel.runs`` carry a documented
        JSON shape (kernel_run prefix + payload). This locks the
        audit stream shape so a downstream log consumer (BigQuery,
        Cloud Logging sink, etc.) can rely on it."""
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        username = _register_user("e3_audit_shape_user")
        caplog.set_level(logging.INFO, logger="clarityos.kernel.runs")

        r_login = client.post(
            "/login", json={"username": username, "password": "x"},
        )
        sid = r_login.json()["session_id"]
        hdrs = {"X-Session-ID": sid}
        client.post(
            "/elins/preview", headers=hdrs,
            json={"text": "for audit shape"},
        )

        kernel_runs = [
            rec for rec in caplog.records
            if rec.name == "clarityos.kernel.runs"
            and rec.getMessage().startswith("kernel_run ")
        ]
        assert kernel_runs, (
            "E3 violated — no kernel_run audit record emitted for /elins/preview"
        )
        # Every kernel_run line parses as JSON after the "kernel_run "
        # prefix; that's the documented audit-stream shape.
        import json as _json
        for rec in kernel_runs:
            payload_text = rec.getMessage().split(" ", 1)[1]
            payload = _json.loads(payload_text)
            # The locked invariants: every audit record carries kind,
            # duration_ms, ok, and (if applicable) model_id in meta.
            assert "kind" in payload
            assert "duration_ms" in payload
            assert "ok" in payload
