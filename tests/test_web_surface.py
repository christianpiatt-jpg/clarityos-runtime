"""Tests for the v0.2.0 Web Surface handler skeleton.

These tests exercise web_surface.py in isolation via a small ad-hoc
FastAPI app, so they do not depend on the full ClarityOS runtime
app.py being importable in the test environment. They lock in:

  * the disabled-by-default behavior (503 when the flag is unset)
  * the enabled stub behavior (501 from any path under the prefix)
  * the describe() metadata shape
  * the flag parser tolerating whitespace/case
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import web_surface


@pytest.fixture
def client_disabled(monkeypatch):
    monkeypatch.delenv(web_surface.WEB_SURFACE_FLAG_ENV, raising=False)
    importlib.reload(web_surface)
    app = FastAPI()
    app.include_router(web_surface.router)
    return TestClient(app)


@pytest.fixture
def client_enabled(monkeypatch):
    monkeypatch.setenv(web_surface.WEB_SURFACE_FLAG_ENV, "true")
    importlib.reload(web_surface)
    app = FastAPI()
    app.include_router(web_surface.router)
    return TestClient(app)


def test_disabled_returns_503(client_disabled):
    resp = client_disabled.get("/web-surface/v0.2/anything")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"] == "web_surface_disabled"
    assert web_surface.WEB_SURFACE_FLAG_ENV in body["detail"]


def test_enabled_returns_501_stub(client_enabled):
    resp = client_enabled.get("/web-surface/v0.2/ping")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"] == "web_surface_not_implemented"
    assert body["version"] == "v0.2.0"
    assert body["path"] == "/web-surface/v0.2/ping"


def test_enabled_root_returns_501(client_enabled):
    resp = client_enabled.get("/web-surface/v0.2")
    assert resp.status_code in (501, 307, 308)
    # follow any redirect FastAPI adds for trailing-slash handling
    if resp.status_code in (307, 308):
        resp = client_enabled.get(resp.headers["location"])
    assert resp.status_code == 501


def test_enabled_accepts_multiple_methods(client_enabled):
    for method in ("get", "post", "put", "patch", "delete"):
        resp = getattr(client_enabled, method)("/web-surface/v0.2/x")
        assert resp.status_code == 501, method


def test_flag_parser_is_case_and_whitespace_tolerant(monkeypatch):
    monkeypatch.setenv(web_surface.WEB_SURFACE_FLAG_ENV, "  TRUE  ")
    importlib.reload(web_surface)
    assert web_surface.is_web_surface_enabled() is True

    monkeypatch.setenv(web_surface.WEB_SURFACE_FLAG_ENV, "false")
    importlib.reload(web_surface)
    assert web_surface.is_web_surface_enabled() is False

    monkeypatch.setenv(web_surface.WEB_SURFACE_FLAG_ENV, "1")
    importlib.reload(web_surface)
    assert web_surface.is_web_surface_enabled() is False


def test_describe_shape(monkeypatch):
    monkeypatch.delenv(web_surface.WEB_SURFACE_FLAG_ENV, raising=False)
    importlib.reload(web_surface)
    info = web_surface.describe()
    assert info["surface"] == "web"
    assert info["version"] == "v0.2.0"
    assert info["prefix"] == "/web-surface/v0.2"
    assert info["enabled"] is False
    assert info["flag_env"] == "WEB_SURFACE_V0_2_ENABLED"
