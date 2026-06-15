"""C2 — tests for POST /billing/checkout-link (public, email-only).

The route is public (no X-Session-ID). It rate-limits per IP, soft-checks
Origin against the CORS host allowlist, regex-validates the email, resolves
the Founding price (body -> env -> mock fallback), and returns a Stripe-hosted
Checkout URL. Stripe is stubbed via a fake module injected into sys.modules.
"""
from __future__ import annotations

import sys
import types

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


@pytest.fixture(autouse=True)
def _rl_reset():
    """Per-test rate-limit reset. The route calls ``check_rate_limit``
    directly, which is live in tests (``CLARITYOS_DISABLE_AUTH_RATE_LIMIT=1``
    disables ``_throttle_auth`` only, not ``check_rate_limit``). The test
    client uses a constant IP, so without a per-test reset the shared
    5-token bucket would deplete across tests."""
    import v29_hardening
    v29_hardening._reset_rate_limits_for_tests()
    yield


@pytest.fixture
def _with_stripe_key(monkeypatch):
    """Truthy secret key for tests that reach the helper. Without it,
    ``billing_config.get_secret_key()`` returns None -> the explicit 503
    guard fires before the stubbed ``Session.create``."""
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_x")


class _FakeSession:
    last_kwargs = None

    @staticmethod
    def create(**kwargs):
        _FakeSession.last_kwargs = kwargs
        return types.SimpleNamespace(
            url="https://checkout.stripe.com/c/pay/cs_test_fake_123"
        )


class _FakeCustomer:
    """CL-17 — stub for stripe.Customer.create / retrieve so the new upstream
    customer-resolution path is exercisable. Harness extension only; not an
    intent change to the 11 existing public/email-keyed tests."""
    created_with = None

    @staticmethod
    def create(**kwargs):
        _FakeCustomer.created_with = kwargs
        return types.SimpleNamespace(id="cus_test_new_123")

    @staticmethod
    def retrieve(cid):
        # ids prefixed 'cus_deleted' simulate a Stripe-deleted Customer.
        return types.SimpleNamespace(id=cid, deleted=str(cid).startswith("cus_deleted"))


def _inject_fake_stripe(monkeypatch):
    """Inject a fake ``stripe`` module exposing ``checkout.Session.create().url``
    plus ``Customer.create`` / ``Customer.retrieve`` (CL-17 resolution)."""
    _FakeSession.last_kwargs = None
    _FakeCustomer.created_with = None
    fake = types.ModuleType("stripe")
    fake.api_key = None
    fake.checkout = types.SimpleNamespace(Session=_FakeSession)
    fake.Customer = _FakeCustomer
    monkeypatch.setitem(sys.modules, "stripe", fake)
    return _FakeSession


_GOOD_ORIGIN = {"origin": "https://pro-mediations.com"}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_happy_path(app_module, client, monkeypatch, _with_stripe_key):
    _inject_fake_stripe(monkeypatch)
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["checkout_url"].startswith("https://checkout.stripe.com/")


# ---------------------------------------------------------------------------
# Email validation (reject before reaching the helper)
# ---------------------------------------------------------------------------
def test_missing_email(app_module, client):
    r = client.post("/billing/checkout-link", json={}, headers=_GOOD_ORIGIN)
    assert r.status_code == 422


def test_bad_email_format(app_module, client):
    r = client.post(
        "/billing/checkout-link",
        json={"email": "notanemail"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Origin allowlist (hostname-suffix via urlparse, not substring)
# ---------------------------------------------------------------------------
def test_origin_rejected(app_module, client):
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com"},
        headers={"origin": "https://evil.com"},
    )
    assert r.status_code == 403


def test_origin_substring_attack(app_module, client, monkeypatch, _with_stripe_key):
    _inject_fake_stripe(monkeypatch)
    # Host CONTAINS an allowed host as a substring but is NOT it -> 403.
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com"},
        headers={"origin": "https://clarity.pro-mediations.com.evil.net"},
    )
    assert r.status_code == 403


def test_origin_absent_ok(app_module, client, monkeypatch, _with_stripe_key):
    _inject_fake_stripe(monkeypatch)
    # Server-side WP -> engine: no Origin/Referer -> passes through.
    r = client.post("/billing/checkout-link", json={"email": "buyer@example.com"})
    assert r.status_code == 200, r.json()


# ---------------------------------------------------------------------------
# Rate limit (capacity 5 / 10 min / IP)
# ---------------------------------------------------------------------------
def test_rate_limited(app_module, client, monkeypatch, _with_stripe_key):
    _inject_fake_stripe(monkeypatch)
    last = None
    for _ in range(6):
        last = client.post(
            "/billing/checkout-link",
            json={"email": "buyer@example.com"},
            headers=_GOOD_ORIGIN,
        )
    assert last.status_code == 429


# ---------------------------------------------------------------------------
# Billing not configured -> 503 (intentionally no _with_stripe_key)
# ---------------------------------------------------------------------------
def test_no_secret_key(app_module, client, monkeypatch):
    import billing_config
    monkeypatch.setattr(billing_config, "get_secret_key", lambda: None)
    _inject_fake_stripe(monkeypatch)
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# Price resolution + plan threading
# ---------------------------------------------------------------------------
def test_price_resolution_env_default(app_module, client, monkeypatch, _with_stripe_key):
    fake = _inject_fake_stripe(monkeypatch)
    monkeypatch.setenv("CLARITYOS_STRIPE_PRICE_FOUNDING", "price_env_default")
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["line_items"][0]["price"] == "price_env_default"


def test_price_resolution_body_override(app_module, client, monkeypatch, _with_stripe_key):
    fake = _inject_fake_stripe(monkeypatch)
    monkeypatch.setenv("CLARITYOS_STRIPE_PRICE_FOUNDING", "price_env_default")
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com", "price_id": "price_body_xyz"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["line_items"][0]["price"] == "price_body_xyz"


def test_plan_threaded(app_module, client, monkeypatch, _with_stripe_key):
    fake = _inject_fake_stripe(monkeypatch)
    r = client.post(
        "/billing/checkout-link",
        json={"email": "buyer@example.com", "plan": "annual"},
        headers=_GOOD_ORIGIN,
    )
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["metadata"]["plan"] == "annual"


# ---------------------------------------------------------------------------
# CL-17 — upstream customer resolution (preserve-public reconciliation).
# Every Checkout now receives customer=<id>; NO customer_email= mint.
# ---------------------------------------------------------------------------
def test_cl17_case_a_reuses_existing_customer(app_module, client, monkeypatch, _with_stripe_key):
    """User-doc with a non-deleted stripe_customer_id -> REUSE it; no new
    Customer minted, no user-doc write."""
    fake = _inject_fake_stripe(monkeypatch)
    import users_store
    users_store.create_user(username="buyer@example.com", password_hash=b"x",
                            salt="", tier="free", created_at=0.0)
    users_store.update_user("buyer@example.com", {"stripe_customer_id": "cus_existing_live"})
    r = client.post("/billing/checkout-link", json={"email": "buyer@example.com"},
                    headers=_GOOD_ORIGIN)
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["customer"] == "cus_existing_live"
    assert "customer_email" not in fake.last_kwargs           # no implicit mint
    assert _FakeCustomer.created_with is None                  # no Customer.create
    assert users_store.get_user("buyer@example.com")["stripe_customer_id"] == "cus_existing_live"


def test_cl17_case_b_empty_field_creates_and_writes_back(app_module, client, monkeypatch, _with_stripe_key):
    """User-doc exists but lacks stripe_customer_id -> create Customer +
    conditional write-back."""
    fake = _inject_fake_stripe(monkeypatch)
    import users_store
    users_store.create_user(username="buyer@example.com", password_hash=b"x",
                            salt="", tier="free", created_at=0.0)
    r = client.post("/billing/checkout-link", json={"email": "buyer@example.com"},
                    headers=_GOOD_ORIGIN)
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["customer"] == "cus_test_new_123"
    assert _FakeCustomer.created_with == {"email": "buyer@example.com"}
    assert users_store.get_user("buyer@example.com")["stripe_customer_id"] == "cus_test_new_123"


def test_cl17_case_b_deleted_customer_replaced(app_module, client, monkeypatch, _with_stripe_key):
    """User-doc points at a DELETED Customer -> create new + write over the
    non-functional id (documented exception)."""
    fake = _inject_fake_stripe(monkeypatch)
    import users_store
    users_store.create_user(username="buyer@example.com", password_hash=b"x",
                            salt="", tier="free", created_at=0.0)
    users_store.update_user("buyer@example.com", {"stripe_customer_id": "cus_deleted_old"})
    r = client.post("/billing/checkout-link", json={"email": "buyer@example.com"},
                    headers=_GOOD_ORIGIN)
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["customer"] == "cus_test_new_123"
    assert users_store.get_user("buyer@example.com")["stripe_customer_id"] == "cus_test_new_123"


def test_cl17_case_c_new_buyer_no_userdoc_write(app_module, client, monkeypatch, _with_stripe_key):
    """No user-doc yet -> create Customer, but DO NOT write a user-doc at this
    layer (webhook binds it later via CL-19)."""
    fake = _inject_fake_stripe(monkeypatch)
    import users_store
    assert users_store.get_user("buyer@example.com") is None
    r = client.post("/billing/checkout-link", json={"email": "buyer@example.com"},
                    headers=_GOOD_ORIGIN)
    assert r.status_code == 200, r.json()
    assert fake.last_kwargs["customer"] == "cus_test_new_123"
    assert _FakeCustomer.created_with == {"email": "buyer@example.com"}
    assert users_store.get_user("buyer@example.com") is None   # no write at this layer
