"""
Regression tests for FIX-C1 (PASS-4) — bootstrap admin password to mandatory
env var.

Goal: eliminate bootstrap admin password exposure via stdout / Cloud Logging
by refusing to boot without CLARITYOS_ADMIN_PASSWORD when
CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED is "true".

Tests cover:
    A. Missing password + required flag → RuntimeError; no print/log output.
    B. Provided password + required flag → admin created with bcrypt hash of
       the provided password; no print/log output containing the password.
    C. Legacy mode (required flag absent or "false", no env password) →
       legacy random + print behaviour preserved (until deprecation).
"""
from __future__ import annotations

import importlib
import io
import logging
import os
import sys
from contextlib import redirect_stdout

import bcrypt
import pytest


@pytest.fixture
def fresh_env(monkeypatch):
    """Clear the three env vars FIX-C1 cares about; restore on exit."""
    for var in (
        "CLARITYOS_ADMIN_USER",
        "CLARITYOS_ADMIN_PASSWORD",
        "CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED",
    ):
        monkeypatch.delenv(var, raising=False)
    # Force memory backend so we don't touch Firestore in tests.
    monkeypatch.setenv("CLARITYOS_BACKEND", "memory")
    # Vault master secret is required by memory_vault on import — set a
    # deterministic test value so any transitive vault import succeeds.
    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "fix-c1-test-secret")
    yield


@pytest.fixture
def reload_app_module(fresh_env, monkeypatch):
    """
    Reload `app` so `_bootstrap_admin` runs against the current env.

    Returns the freshly-imported `app` module. Captures stdout during the
    reload so tests can assert on what was (or wasn't) printed.
    """
    # Drop the cached module so we get a fresh module-load side effect.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    # Also wipe users_store memory so the admin user doesn't already exist.
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    captured = io.StringIO()
    with redirect_stdout(captured):
        import app  # noqa: F401 — module side effect is the test target
    app_module = sys.modules["app"]
    app_module.__test_captured_stdout__ = captured.getvalue()
    return app_module


# ---------------------------------------------------------------------------
# Test A — required + missing password → RuntimeError
# ---------------------------------------------------------------------------
def test_missing_password_required_raises_runtimeerror(fresh_env, monkeypatch, caplog):
    """
    With CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED=true and no
    CLARITYOS_ADMIN_PASSWORD, _bootstrap_admin must raise RuntimeError.

    Side effects to verify:
      - RuntimeError is raised at module load (because _bootstrap_admin runs
        at import time via `_admin_pwd_source = _bootstrap_admin()`).
      - No password generation occurs (no secrets.token_urlsafe).
      - No stdout output containing a password.
      - No log records contain a password.
    """
    monkeypatch.setenv("CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED", "true")
    # CLARITYOS_ADMIN_PASSWORD intentionally unset (handled by fresh_env).

    # Drop cached app module so import re-runs the bootstrap.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    captured = io.StringIO()
    with caplog.at_level(logging.DEBUG, logger="clarityos"):
        with redirect_stdout(captured):
            with pytest.raises(RuntimeError) as exc:
                import app  # noqa: F401

    msg = str(exc.value)
    assert "CLARITYOS_ADMIN_PASSWORD is required" in msg
    assert "refusing to generate" in msg

    # No password generation → no random-token bootstrap line appears.
    out = captured.getvalue()
    assert "ClarityOS bootstrap admin" not in out
    assert "password:" not in out

    # No log line carries any indication of a generated password.
    for record in caplog.records:
        assert "password" not in record.getMessage().lower() or (
            "required" in record.getMessage().lower()
        )


# ---------------------------------------------------------------------------
# Test B — required + provided password → admin created, no leakage
# ---------------------------------------------------------------------------
def test_provided_password_required_creates_admin_silently(
    fresh_env, monkeypatch, caplog,
):
    """
    With CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED=true and
    CLARITYOS_ADMIN_PASSWORD set, _bootstrap_admin must:
      - Create the admin user.
      - Store a bcrypt hash that verifies against the provided password.
      - Produce no stdout output containing the password.
      - Produce no log line containing the password.
      - Return "env" as the source.
    """
    known_pwd = "knownvalue-deterministic-test-pwd"
    monkeypatch.setenv("CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED", "true")
    monkeypatch.setenv("CLARITYOS_ADMIN_PASSWORD", known_pwd)

    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    captured = io.StringIO()
    with caplog.at_level(logging.DEBUG, logger="clarityos"):
        with redirect_stdout(captured):
            import app  # noqa: F401

    # Source must be "env" (no random generation path).
    assert app._admin_pwd_source == "env"

    # Admin user exists and the stored hash verifies against the provided pwd.
    admin = users_store.get_user("admin") or {}
    assert admin, "admin user was not created"
    stored_hash = admin.get("password_hash")
    assert stored_hash, "admin user has no password_hash"
    # Stored hash is bytes (per _create_user using bcrypt.hashpw without decode);
    # bcrypt.checkpw accepts bytes-or-str on input but bytes on hash.
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode("utf-8")
    assert bcrypt.checkpw(known_pwd.encode("utf-8"), stored_hash)

    # No stdout leakage.
    out = captured.getvalue()
    assert known_pwd not in out
    assert "ClarityOS bootstrap admin" not in out
    assert "password:" not in out

    # No log leakage.
    for record in caplog.records:
        assert known_pwd not in record.getMessage()


# ---------------------------------------------------------------------------
# Test C — legacy mode preserved (until deprecation)
# ---------------------------------------------------------------------------
def test_legacy_mode_preserves_random_generation_and_print(fresh_env, monkeypatch):
    """
    With CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED unset (or "false") AND
    CLARITYOS_ADMIN_PASSWORD unset, the legacy random-password + print
    behaviour must be preserved. This documents the transition path; the
    legacy branch is scheduled for removal after the flag is flipped to
    "true" globally.
    """
    # Required flag absent → defaults to legacy behaviour.
    # CLARITYOS_ADMIN_PASSWORD intentionally unset.

    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    captured = io.StringIO()
    with redirect_stdout(captured):
        import app  # noqa: F401

    # Source must be "generated" (legacy random path).
    assert app._admin_pwd_source == "generated"

    # Legacy print output is preserved.
    out = captured.getvalue()
    assert "ClarityOS bootstrap admin" in out
    assert "password:" in out
    assert "Set CLARITYOS_ADMIN_USER / CLARITYOS_ADMIN_PASSWORD to override." in out

    # Admin user was created.
    admin = users_store.get_user("admin") or {}
    assert admin, "admin user was not created in legacy mode"
    assert admin.get("password_hash"), "admin user has no password_hash"


# ---------------------------------------------------------------------------
# Test D — required + "false" string variants are treated as legacy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flag_value", ["false", "0", "no", "", "FALSE", "False"])
def test_required_flag_falsy_values_use_legacy_path(fresh_env, monkeypatch, flag_value):
    """
    CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED must default-False on anything
    other than the canonical "true" (case-insensitive). Belt-and-suspenders
    check that the flag does not accidentally enforce strict mode on stray
    values.
    """
    monkeypatch.setenv("CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED", flag_value)
    # No CLARITYOS_ADMIN_PASSWORD set; legacy path must succeed.

    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    captured = io.StringIO()
    with redirect_stdout(captured):
        import app  # noqa: F401

    assert app._admin_pwd_source == "generated"


# ---------------------------------------------------------------------------
# Test E — required + "TRUE"/"True" treated as true (case-insensitive)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flag_value", ["true", "True", "TRUE", "  true  "])
def test_required_flag_truthy_values_enforce_strict_mode(
    fresh_env, monkeypatch, flag_value,
):
    """The required flag must be case-insensitive and whitespace-tolerant."""
    monkeypatch.setenv("CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED", flag_value)
    # No CLARITYOS_ADMIN_PASSWORD set — must raise.

    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            sys.modules.pop(mod, None)
    import users_store
    if hasattr(users_store, "_reset_memory_for_tests"):
        users_store._reset_memory_for_tests()

    with pytest.raises(RuntimeError, match="CLARITYOS_ADMIN_PASSWORD is required"):
        import app  # noqa: F401
