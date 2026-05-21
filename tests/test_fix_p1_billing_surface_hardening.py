"""
PASS-4 FIX-P1 — Billing-surface privacy & state mapping hardening.

Two narrow fixes on existing routes in ``app.py``:

  1. ``POST /billing/intent/confirm`` — the response previously
     embedded the full ``billing_intents.confirm_payment_intent``
     return dict under ``intent``, which leaked
     ``client_secret`` and the raw provider ``metadata`` (user_id,
     cohort, environment, etc.) to the client. The mock-confirm flow
     has no client-side Stripe.js step that needs ``client_secret``,
     so we redact those fields and project a safe shape that matches
     the existing ``/billing/history`` per-intent projection.

  2. ``GET /me/billing`` — ``billing_state == "failed"`` previously
     fell through to ``status: "none"``, collapsing an
     activation-failure case into "no billing". Now mapped to a
     distinct ``status: "failed"``.

  3. Logging discipline — neither route may log ``client_secret`` or
     the raw provider metadata on the happy path.

These tests focus on the V2 mitigation only. The existing v31 / v42
tests cover the rest of the billing flow and continue to pass
unchanged.
"""
from __future__ import annotations

import logging
import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, *, cohort="founder",
               billing_state=None, renewal_ts=None):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    patch: dict = {}
    if cohort:
        patch["cohort"] = cohort
    if billing_state is not None:
        patch["billing_state"] = billing_state
    if renewal_ts is not None:
        patch["renewal_ts"] = float(renewal_ts)
    if patch:
        users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid: str) -> dict:
    return {"X-Session-ID": sid}


# ===========================================================================
# Test A — /billing/intent/confirm redaction
# ===========================================================================
class TestConfirmRedaction:
    """The confirm response must NOT carry ``client_secret`` or the raw
    provider ``metadata`` dict. The mock-confirm flow has already taken
    the server-side side effect; the client has no Stripe.js step that
    would need ``client_secret``."""

    def test_confirm_response_omits_client_secret(self, app_module, client, manual_confirm):
        import billing_intents
        user, sid = _make_user(app_module, "p1_confirm_a", cohort="founder")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "single credit", kind="g_credit_single",
        )
        # Sanity: the underlying record DOES have a client_secret —
        # this is what makes the redaction load-bearing.
        assert intent.get("client_secret")

        r = client.post(
            "/billing/intent/confirm", headers=_auth(sid),
            json={"intent_id": intent["intent_id"]},
        )
        assert r.status_code == 200, r.json()
        body = r.json()

        assert body["ok"] is True
        assert "intent" in body
        out = body["intent"]

        # The redacted response carries only safe fields.
        assert "client_secret" not in out
        # The full serialised body must also not contain client_secret
        # anywhere (defence-in-depth — catches accidental nesting).
        serialised = repr(body)
        assert "client_secret" not in serialised

    def test_confirm_response_omits_raw_metadata(self, app_module, client, manual_confirm):
        import billing_intents
        user, sid = _make_user(app_module, "p1_confirm_b", cohort="founder")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "single credit", kind="g_credit_single",
            metadata={"campaign": "spring-2026", "internal_note": "test"},
        )
        r = client.post(
            "/billing/intent/confirm", headers=_auth(sid),
            json={"intent_id": intent["intent_id"]},
        )
        body = r.json()
        out = body["intent"]
        # Raw provider metadata is not exposed.
        assert "metadata" not in out
        # And no specific metadata value leaks in the serialised body.
        serialised = repr(body)
        assert "campaign" not in serialised
        assert "spring-2026" not in serialised
        assert "internal_note" not in serialised

    def test_confirm_response_preserves_safe_fields(self, app_module, client, manual_confirm):
        """The redacted response must still expose the fields the
        frontend legitimately reads — intent_id, status, amount, kind,
        mode, description, created/confirmed timestamps, and any
        failure indicator. Mirrors /billing/history's projection."""
        import billing_intents
        user, sid = _make_user(app_module, "p1_confirm_c", cohort="founder")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "single credit", kind="g_credit_single",
        )
        r = client.post(
            "/billing/intent/confirm", headers=_auth(sid),
            json={"intent_id": intent["intent_id"]},
        )
        body = r.json()
        out = body["intent"]

        for field in (
            "intent_id", "status", "amount", "kind", "mode",
            "description", "created_ts", "confirmed_ts",
            "failed_ts", "failure_code",
        ):
            assert field in out, f"{field!r} missing from /billing/intent/confirm payload"

        assert out["intent_id"] == intent["intent_id"]
        assert out["status"] == "succeeded"
        assert out["kind"] == "g_credit_single"

    def test_confirm_response_route_shape_unchanged(self, app_module, client, manual_confirm):
        """The top-level shape (``ok`` + ``intent``) is preserved.
        FIX-P1 only narrows the contents of ``intent``."""
        import billing_intents
        user, sid = _make_user(app_module, "p1_confirm_d", cohort="founder")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "x", kind="g_credit_single",
        )
        r = client.post(
            "/billing/intent/confirm", headers=_auth(sid),
            json={"intent_id": intent["intent_id"]},
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) >= {"ok", "intent"}
        assert isinstance(body["intent"], dict)


# ===========================================================================
# Test B — /me/billing status mapping (failed ≠ none)
# ===========================================================================
class TestMeBillingStatusMapping:
    def test_failed_billing_state_maps_to_failed(self, app_module, client):
        """The headline FIX-P1 mapping: ``failed`` no longer collapses
        into ``none``."""
        user, sid = _make_user(
            app_module, "p1_status_failed", cohort="founder",
            billing_state="failed",
        )
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "failed"
        assert body["status"] != "none"

    def test_none_billing_state_maps_to_none(self, app_module, client):
        """A user with no billing_state at all is still ``none``."""
        user, sid = _make_user(app_module, "p1_status_none", cohort="founder")
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.status_code == 200
        assert r.json()["status"] == "none"

    def test_existing_active_mapping_unchanged(self, app_module, client):
        user, sid = _make_user(
            app_module, "p1_status_active", cohort="founder",
            billing_state="active", renewal_ts=time.time() + 86400 * 30,
        )
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.json()["status"] == "active"

    def test_existing_past_due_mapping_unchanged(self, app_module, client):
        user, sid = _make_user(
            app_module, "p1_status_past_due", cohort="founder",
            billing_state="past_due",
        )
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.json()["status"] == "past_due"

    def test_existing_grace_period_maps_to_past_due(self, app_module, client):
        """grace_period is collapsed into past_due on the public
        surface (existing v42 behaviour). FIX-P1 must not change that."""
        user, sid = _make_user(
            app_module, "p1_status_grace", cohort="founder",
            billing_state="grace_period",
        )
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.json()["status"] == "past_due"

    def test_existing_cancelled_mapping_unchanged(self, app_module, client):
        user, sid = _make_user(
            app_module, "p1_status_cancelled", cohort="founder",
            billing_state="cancelled",
        )
        r = client.get("/me/billing", headers=_auth(sid))
        assert r.json()["status"] == "canceled"

    def test_response_keys_unchanged(self, app_module, client):
        """The set of response keys is preserved; FIX-P1 only adjusts
        the mapping logic, never the contract."""
        user, sid = _make_user(
            app_module, "p1_keys", cohort="founder",
            billing_state="failed",
        )
        r = client.get("/me/billing", headers=_auth(sid))
        body = r.json()
        for key in ("ok", "status", "plan", "renewal_ts", "mode", "billing_enabled"):
            assert key in body, f"{key!r} missing from /me/billing payload"


# ===========================================================================
# Test C — No sensitive logging
# ===========================================================================
class TestNoSensitiveLogging:
    """The confirm route must not log the full intent dict, the
    ``client_secret``, or the raw provider ``metadata`` anywhere in the
    log stream. We capture every record emitted during the request and
    scan all formatted output."""

    def test_confirm_does_not_log_client_secret_or_metadata(
        self, app_module, client, manual_confirm, caplog,
    ):
        import billing_intents
        user, sid = _make_user(app_module, "p1_log_a", cohort="founder")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "x", kind="g_credit_single",
            metadata={"campaign": "spring-2026"},
        )
        secret_val = intent["client_secret"]

        # Capture across all of ClarityOS's loggers at the lowest
        # interesting level. We do not pin a specific logger name
        # because v29_hardening emits structured log lines via a
        # generic logger that the route doesn't own.
        caplog.set_level(logging.DEBUG)

        r = client.post(
            "/billing/intent/confirm", headers=_auth(sid),
            json={"intent_id": intent["intent_id"]},
        )
        assert r.status_code == 200

        # Walk every record, build the same formatted text the user
        # would see in their log shipper.
        all_messages = "\n".join(
            (rec.getMessage() or "") + " " + repr(getattr(rec, "args", None))
            for rec in caplog.records
        )
        assert "client_secret" not in all_messages
        assert secret_val not in all_messages
        # Metadata values likewise are not surfaced.
        assert "campaign" not in all_messages
        assert "spring-2026" not in all_messages

    def test_me_billing_does_not_log_secret_state(
        self, app_module, client, caplog,
    ):
        """/me/billing is a read endpoint with no Stripe secrets in
        scope — but defensively confirm no record carries the
        ``client_secret`` literal or any Stripe id prefix."""
        user, sid = _make_user(
            app_module, "p1_log_b", cohort="founder",
            billing_state="failed",
        )
        caplog.set_level(logging.DEBUG)

        r = client.get("/me/billing", headers=_auth(sid))
        assert r.status_code == 200

        all_messages = "\n".join(
            (rec.getMessage() or "") + " " + repr(getattr(rec, "args", None))
            for rec in caplog.records
        )
        for forbidden in ("client_secret", "cus_", "sub_", "in_", "pi_"):
            assert forbidden not in all_messages, (
                f"sensitive token {forbidden!r} appeared in /me/billing logs"
            )
