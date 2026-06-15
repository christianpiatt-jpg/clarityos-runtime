"""C3 — webhook hardening regression tests.

Pins the failure mode the pre-C3 production webhook exhibited but the existing
suite could not see (HSI-WEBHOOK-CI-BLIND):

  The live webhook routed through ``billing._stripe()``, whose ``is_configured()``
  gate demands the legacy ``STRIPE_PRICE_ONETIME`` / ``STRIPE_PRICE_RECURRING``
  env vars removed under Doctrine #74 — so every signed delivery 503'd with
  ``billing_not_configured`` *before* the signature was even checked. Every v42
  stripe-mode test masked this by (a) setting those price vars and (b)
  monkeypatching ``billing.verify_webhook``. The test below does NEITHER: it
  mirrors prod's missing-price-vars posture and lets the real gate run.

Plus a guard that the C3 rewiring onto ``billing_config.audit_seen`` /
``audit_begin`` still dedupes duplicate event ids.
"""
from __future__ import annotations

import time

import pytest

from conftest import TestClient


@pytest.fixture
def client(reset_stores):
    import app as app_mod
    return TestClient(app_mod.app)


def test_verify_webhook_works_without_legacy_price_vars(client, monkeypatch):
    """Signed event, real ``verify_webhook``, NO legacy price vars set (prod
    Doctrine #74 posture). The handler must get PAST ``billing._stripe()`` into
    real signature checking — i.e. 400 ``bad_signature``, NOT 503
    ``billing_not_configured``. Pre-C3 this returned 503."""
    import sys
    import types
    # Inject a minimal fake ``stripe`` module so this runs without the real SDK
    # installed (some envs lack it) while still exercising the REAL
    # verify_webhook gate. ``construct_event`` raises → the signature "fails"
    # *after* the gate, proving we got past billing._stripe()/is_configured().
    fake_stripe = types.ModuleType("stripe")
    fake_stripe.api_key = None

    class _Webhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            raise Exception("simulated bad signature")

    fake_stripe.Webhook = _Webhook
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)

    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    # Mirror production: the legacy price vars are NOT present.
    monkeypatch.delenv("STRIPE_PRICE_ONETIME", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_RECURRING", raising=False)

    r = client.post(
        "/billing/webhook",
        json={"id": "evt_c3_1", "type": "checkout.session.completed",
              "data": {"object": {}}},
        headers={"Stripe-Signature": "t=0,v1=deadbeef"},
    )
    assert r.status_code != 503, r.json()
    assert r.status_code == 400
    assert r.json()["error"] == "bad_signature"


def test_duplicate_event_returns_fast_path(client, monkeypatch):
    """The durable-idempotency rewiring still dedupes: the same event id posted
    twice → the second is the duplicate fast-path 200."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    event = {
        "id": "evt_c3_dup", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_x", "payment_status": "paid", "amount_total": 5000,
            "metadata": {"user_id": "alice", "plan": "founding"},
        }},
    }
    r1 = client.post("/billing/webhook", json=event)
    assert r1.status_code == 200
    assert r1.json().get("duplicate") is not True
    r2 = client.post("/billing/webhook", json=event)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True


# ---------------------------------------------------------------------------
# EDIT 3 — Fork A: passwordless email-keyed provisioning
# ---------------------------------------------------------------------------
def test_existing_user_activation_binds_customer_id(client, monkeypatch):
    """Existing user + checkout.session.completed → billing active + the Stripe
    customer id bound to the user doc (so later customer.subscription.* events
    resolve). Existing users are NOT marked stripe-webhook-provisioned."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="buyer@example.com", password_hash=b"pw", salt="",
        tier="free", created_at=time.time(),
    )
    event = {
        "id": "evt_c3_existing", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_e", "payment_status": "paid", "amount_total": 5000,
            "customer": "cus_existing",
            "customer_details": {"email": "buyer@example.com"},
            "metadata": {"plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    u = users_store.get_user("buyer@example.com") or {}
    assert u.get("stripe_customer_id") == "cus_existing"
    assert u.get("billing_state") == "active"
    assert u.get("provisioned_via") != "stripe_webhook"


def test_new_user_provisioning_creates_passwordless_shell(client, monkeypatch):
    """Brand-new buyer email → passwordless shell created (username=email,
    unusable bcrypt password so /login can't claim it), customer id bound,
    billing active, provisioned_via marker set. No `requires_claim` flag — the
    unusable password is the claim gate, matching the magic-link model."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    assert users_store.get_user("new@example.com") is None
    event = {
        "id": "evt_c3_new", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_n", "payment_status": "paid", "amount_total": 5000,
            "customer": "cus_new",
            "customer_details": {"email": "new@example.com"},
            "metadata": {"plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    u = users_store.get_user("new@example.com")
    assert u is not None
    assert u.get("provisioned_via") == "stripe_webhook"
    assert u.get("stripe_customer_id") == "cus_new"
    assert u.get("billing_state") == "active"
    # Unusable password: _ensure_user sets a bcrypt hash of a random token.
    assert u.get("password_hash")


def test_provisioning_uses_existing_magic_link_helper(client, monkeypatch):
    """Provisioning must route through the existing magic-link helper
    (auth_magiclink._ensure_user) — never a new account-creation path."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import auth_magiclink
    calls = {}
    real_ensure = auth_magiclink._ensure_user

    def _spy(email, now):
        calls["email"] = email
        return real_ensure(email, now)

    monkeypatch.setattr(auth_magiclink, "_ensure_user", _spy)
    event = {
        "id": "evt_c3_helper", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_h", "payment_status": "paid", "amount_total": 5000,
            "customer": "cus_h",
            "customer_details": {"email": "helper@example.com"},
            "metadata": {"plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    assert calls.get("email") == "helper@example.com"


def test_missing_email_acknowledged_gracefully(client, monkeypatch):
    """checkout.session.completed with no resolvable email → acknowledged 200
    (no crash, no Stripe retry loop), and no account provisioned."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    before = set(users_store.list_all_usernames())
    event = {
        "id": "evt_c3_noemail", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_ne", "payment_status": "paid", "amount_total": 5000,
            "metadata": {"plan": "founding"},  # no email anywhere
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    after = set(users_store.list_all_usernames())
    assert before == after


def test_cl19_mismatch_preserves_primary_and_audits(client, monkeypatch):
    """CL-19: an existing user-doc whose stripe_customer_id differs from the
    event's customer is NOT overwritten; the mismatch lands in passive audit
    fields and the primary is preserved (the FRAGO 12.04 §3 root cause)."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(username="buyer@example.com", password_hash=b"pw",
                            salt="", tier="free", created_at=time.time())
    users_store.update_user("buyer@example.com", {"stripe_customer_id": "cus_A"})
    event = {
        "id": "evt_cl19_mismatch", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_m", "payment_status": "paid", "amount_total": 5000,
            "customer": "cus_B",
            "customer_details": {"email": "buyer@example.com"},
            "metadata": {"plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    u = users_store.get_user("buyer@example.com") or {}
    assert u.get("stripe_customer_id") == "cus_A"          # primary preserved
    assert u.get("_cl19_mismatch_incoming") == "cus_B"
    assert u.get("_cl19_mismatch_existing") == "cus_A"
    assert u.get("_cl19_mismatch_observed_at")             # ISO timestamp present


def test_cl19_idempotent_match_writes_no_audit(client, monkeypatch):
    """CL-19: when the event's customer equals the existing id, it's a no-op —
    no audit fields written, primary unchanged."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(username="match@example.com", password_hash=b"pw",
                            salt="", tier="free", created_at=time.time())
    users_store.update_user("match@example.com", {"stripe_customer_id": "cus_same"})
    event = {
        "id": "evt_cl19_match", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_s", "payment_status": "paid", "amount_total": 5000,
            "customer": "cus_same",
            "customer_details": {"email": "match@example.com"},
            "metadata": {"plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    u = users_store.get_user("match@example.com") or {}
    assert u.get("stripe_customer_id") == "cus_same"
    assert "_cl19_mismatch_observed_at" not in u

