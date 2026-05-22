"""Tests for the Cloud Run entrypoint at ``web_surface_entry.py``.

The entry module is the standalone Cloud Run-side wiring for the
v0.2.0 Web Surface. These tests lock four contracts:

  1. ``create_web_surface_app()`` returns a FastAPI app whether the
     flag is set or not — never None, never raises at construction.
  2. When the flag is unset (or anything other than the literal
     ``"true"``), the app has zero routes and every request 404s.
  3. When the flag is ``"true"``, the existing ``web_surface.router``
     is included and a request to a sub-path of the prefix returns
     the 501 ``ErrorEnvelope`` stub (Card 7 shape).
  4. The 501 body is schema-conformant: top-level keys are exactly
     ``{error, detail}``.

These tests use the same conftest ``TestClient`` workaround as the
other web_surface tests (httpx >=0.28 broke ``fastapi.testclient``'s
``app=`` kwarg path).
"""
from __future__ import annotations

import importlib

import pytest

# Conftest ``AppClient`` — wraps ``httpx.ASGITransport`` so the test
# client works across httpx versions.
from conftest import TestClient

import web_surface
import web_surface_entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_disabled(monkeypatch):
    """Build a fresh Web Surface app with the flag unset → no routes."""
    monkeypatch.delenv(web_surface_entry.WEB_SURFACE_FLAG_ENV, raising=False)
    # Reload web_surface so its internal flag also matches the fresh env.
    importlib.reload(web_surface)
    importlib.reload(web_surface_entry)
    return web_surface_entry.create_web_surface_app()


@pytest.fixture
def app_enabled(monkeypatch):
    """Build a fresh Web Surface app with the flag explicitly enabled."""
    monkeypatch.setenv(web_surface_entry.WEB_SURFACE_FLAG_ENV, "true")
    importlib.reload(web_surface)
    importlib.reload(web_surface_entry)
    return web_surface_entry.create_web_surface_app()


# ---------------------------------------------------------------------------
# 1. Factory contract — always returns an app
# ---------------------------------------------------------------------------
class TestFactory:
    def test_returns_fastapi_app_when_disabled(self, app_disabled):
        from fastapi import FastAPI
        assert isinstance(app_disabled, FastAPI)

    def test_returns_fastapi_app_when_enabled(self, app_enabled):
        from fastapi import FastAPI
        assert isinstance(app_enabled, FastAPI)

    def test_app_title_pins_v0_2_0(self, app_disabled):
        assert "v0.2.0" in app_disabled.title

    def test_docs_disabled(self, app_disabled):
        # docs_url / redoc_url / openapi_url are all None — the
        # surface is internal; we don't ship its schema publicly.
        assert app_disabled.docs_url is None
        assert app_disabled.redoc_url is None
        assert app_disabled.openapi_url is None


# ---------------------------------------------------------------------------
# 2. Disabled-by-default: zero routes, 404 on every path
# ---------------------------------------------------------------------------
class TestDisabledMount:
    def test_app_has_no_web_surface_routes(self, app_disabled):
        # The app has FastAPI's built-in routes (none, actually — we
        # disabled docs/openapi). Any ``/web-surface/v0.2/*`` route
        # comes from including web_surface.router. When disabled, we
        # don't include it → no such routes.
        route_paths = [getattr(r, "path", "") for r in app_disabled.routes]
        web_surface_routes = [
            p for p in route_paths if p.startswith("/web-surface/v0.2")
        ]
        assert web_surface_routes == [], (
            f"disabled app should expose no web-surface routes; "
            f"got {web_surface_routes!r}"
        )

    def test_get_to_surface_path_returns_404(self, app_disabled):
        client = TestClient(app_disabled)
        resp = client.get("/web-surface/v0.2/anything")
        assert resp.status_code == 404

    def test_get_to_root_returns_404(self, app_disabled):
        client = TestClient(app_disabled)
        resp = client.get("/")
        assert resp.status_code == 404

    def test_post_to_surface_path_returns_404(self, app_disabled):
        client = TestClient(app_disabled)
        resp = client.post(
            "/web-surface/v0.2/echo",
            json={"path": "/x", "method": "GET", "headers": {}, "body": None},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Enabled mount: router included, 501 stub responses
# ---------------------------------------------------------------------------
class TestEnabledMount:
    def test_app_carries_web_surface_routes(self, app_enabled):
        route_paths = [getattr(r, "path", "") for r in app_enabled.routes]
        web_surface_routes = [
            p for p in route_paths if p.startswith("/web-surface/v0.2")
        ]
        assert len(web_surface_routes) > 0, (
            "enabled app should expose web-surface routes"
        )

    def test_get_to_surface_path_returns_501(self, app_enabled):
        client = TestClient(app_enabled)
        resp = client.get("/web-surface/v0.2/echo")
        assert resp.status_code == 501

    def test_post_to_surface_subpath_returns_501(self, app_enabled):
        client = TestClient(app_enabled)
        resp = client.post(
            "/web-surface/v0.2/echo",
            json={
                "path":    "/x",
                "method":  "GET",
                "headers": {},
                "body":    None,
            },
        )
        assert resp.status_code == 501


# ---------------------------------------------------------------------------
# 4. Response body is schema-conformant (Card 7 contract)
# ---------------------------------------------------------------------------
class TestEnabledResponseConformsToEnvelope:
    def test_501_body_has_only_envelope_top_level_keys(self, app_enabled):
        client = TestClient(app_enabled)
        resp = client.get("/web-surface/v0.2/echo")
        body = resp.json()
        # Top-level keys = {error, detail} per Card 7's FIX. No
        # ``path`` / ``version`` / ``message`` at the top level —
        # those nest under ``detail``.
        assert set(body.keys()) == {"error", "detail"}

    def test_501_body_carries_documented_error_code(self, app_enabled):
        client = TestClient(app_enabled)
        resp = client.get("/web-surface/v0.2/echo")
        body = resp.json()
        assert body["error"] == "web_surface_not_implemented"

    def test_501_body_detail_carries_version_pin(self, app_enabled):
        client = TestClient(app_enabled)
        resp = client.get("/web-surface/v0.2/echo")
        body = resp.json()
        assert body["detail"]["version"] == "v0.2.0"

    def test_501_body_re_parses_as_pydantic_envelope(self, app_enabled):
        # End-to-end conformance: the wire body re-parses as a valid
        # ``WebSurfaceV02ErrorEnvelope`` (the Pydantic model auto-
        # generated from the shared schema). If the surface ever
        # returns a body that doesn't conform, this fails.
        from web_surface_models import WebSurfaceV02ErrorEnvelope
        client = TestClient(app_enabled)
        resp = client.get("/web-surface/v0.2/echo")
        env = WebSurfaceV02ErrorEnvelope.model_validate(resp.json())
        assert env.error == "web_surface_not_implemented"


# ---------------------------------------------------------------------------
# 5. Flag-parse tolerance + boundary cases
# ---------------------------------------------------------------------------
class TestFlagParseBoundaries:
    """The flag must match the literal ``"true"`` (case-insensitive,
    whitespace-trimmed). Everything else leaves the app disabled.
    Mirrors the PASS-4 FIX-P3 contract on ``CLARITYOS_VAULT_PLAINTEXT``."""

    @pytest.mark.parametrize("value", ["1", "yes", "True!", "trueish", "0", ""])
    def test_legacy_or_typo_values_leave_app_disabled(
        self, monkeypatch, value,
    ):
        monkeypatch.setenv(web_surface_entry.WEB_SURFACE_FLAG_ENV, value)
        importlib.reload(web_surface)
        importlib.reload(web_surface_entry)
        app = web_surface_entry.create_web_surface_app()
        client = TestClient(app)
        resp = client.get("/web-surface/v0.2/x")
        assert resp.status_code == 404, (
            f"value {value!r} should NOT enable the surface; got "
            f"{resp.status_code}"
        )

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "  true  "])
    def test_explicit_true_enables_surface(self, monkeypatch, value):
        monkeypatch.setenv(web_surface_entry.WEB_SURFACE_FLAG_ENV, value)
        importlib.reload(web_surface)
        importlib.reload(web_surface_entry)
        app = web_surface_entry.create_web_surface_app()
        client = TestClient(app)
        resp = client.get("/web-surface/v0.2/x")
        assert resp.status_code == 501, (
            f"value {value!r} should enable the surface"
        )
