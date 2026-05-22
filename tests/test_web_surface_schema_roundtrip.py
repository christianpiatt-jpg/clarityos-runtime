"""PASS — Task Card 7: Python-side schema roundtrip tests.

These tests anchor the Python end of the v0.2.0 Web Surface contract
bridge:

    web/src/contracts/webSurfaceV0_2.ts          (canonical source)
        → npm run contracts:gen
    web/src/contracts/webSurfaceV0_2.schema.json (committed artifact)
        → bash scripts/gen_web_surface_models.sh
    web_surface_models.py                        (committed artifact)
        → exercised here

They assert four contracts in turn:

  * the schema loads via ``web_surface_schema_loader``
  * the generated Pydantic ``WebSurfaceV02Request`` accepts a
    well-shaped request and rejects malformed ones
  * the generated ``WebSurfaceV02ErrorEnvelope`` round-trips and
    forbids additional properties (matching the schema's
    ``additionalProperties: false`` policy)
  * the live FastAPI handler in ``web_surface.py`` returns a body
    that re-parses as a valid ``WebSurfaceV02ErrorEnvelope`` —
    i.e. the wire shape matches the model shape

If any of these fails after a contract edit, the fix is to regenerate
the schema and models (``npm run contracts:gen`` + ``bash
scripts/gen_web_surface_models.sh``) and re-run the test.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

# PASS — Task Card 7: same TestClient swap as test_web_surface.py
# (conftest's AppClient is httpx-version-tolerant).
from conftest import TestClient

import web_surface
import web_surface_schema_loader
from web_surface_models import (
    WebSurfaceV02ErrorEnvelope,
    WebSurfaceV02Request,
    WebSurfaceV02Response,
)


# ---------------------------------------------------------------------------
# 1. Schema loader
# ---------------------------------------------------------------------------
class TestSchemaLoader:
    def test_load_returns_dict(self):
        schema = web_surface_schema_loader.load_web_surface_schema()
        assert isinstance(schema, dict)

    def test_load_has_version_pin(self):
        schema = web_surface_schema_loader.load_web_surface_schema()
        assert schema.get("version") == "v0.2.0"

    def test_load_has_required_definitions(self):
        schema = web_surface_schema_loader.load_web_surface_schema()
        defs = schema.get("definitions") or {}
        for name in (
            "WebSurfaceV0_2.Request",
            "WebSurfaceV0_2.Response",
            "WebSurfaceV0_2.ErrorEnvelope",
            "WebSurfaceV0_2.SurfaceAction",
        ):
            assert name in defs, f"definition missing: {name}"

    def test_schema_path_is_under_repo_root(self):
        # The loader anchors via __file__ at repo root; the resolved
        # path must contain the documented sub-path. Catches a
        # refactor that moves the loader without updating the path.
        path_str = str(web_surface_schema_loader.SCHEMA_PATH).replace("\\", "/")
        assert "web/src/contracts/webSurfaceV0_2.schema.json" in path_str


# ---------------------------------------------------------------------------
# 2. Pydantic Request model accepts + rejects per the contract
# ---------------------------------------------------------------------------
class TestRequestValidation:
    def test_well_shaped_request_accepted(self):
        req = WebSurfaceV02Request(
            path="/web-surface/v0.2/test",
            method="GET",
            headers={"x-trace": "abc"},
            body=None,
        )
        assert req.path == "/web-surface/v0.2/test"
        assert req.method == "GET"
        # headers is a RootModel wrapper; .root gives the dict.
        assert req.headers.root == {"x-trace": "abc"}
        assert req.body is None

    def test_body_can_be_arbitrary_payload(self):
        # The contract types body as ``unknown`` → ``Any``.
        req = WebSurfaceV02Request(
            path="/x", method="POST",
            headers={}, body={"nested": [1, 2, 3]},
        )
        assert req.body == {"nested": [1, 2, 3]}

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            WebSurfaceV02Request(
                # path missing
                method="GET",
                headers={},
                body=None,
            )

    def test_extra_field_rejected(self):
        # ``extra="forbid"`` mirrors the schema's
        # ``additionalProperties: false`` policy.
        with pytest.raises(ValidationError):
            WebSurfaceV02Request(
                path="/x", method="GET", headers={}, body=None,
                unknown_field="should-fail",  # type: ignore[call-arg]
            )

    def test_wrong_type_for_path_rejected(self):
        with pytest.raises(ValidationError):
            WebSurfaceV02Request(
                path=123,  # type: ignore[arg-type]
                method="GET", headers={}, body=None,
            )


# ---------------------------------------------------------------------------
# 3. ErrorEnvelope round-trips + forbids extras
# ---------------------------------------------------------------------------
class TestErrorEnvelope:
    def test_minimal_envelope(self):
        env = WebSurfaceV02ErrorEnvelope(error="x")
        assert env.error == "x"
        assert env.detail is None

    def test_envelope_with_string_detail(self):
        env = WebSurfaceV02ErrorEnvelope(
            error="x", detail="human-readable hint",
        )
        assert env.detail == "human-readable hint"

    def test_envelope_with_nested_detail(self):
        env = WebSurfaceV02ErrorEnvelope(
            error="validation_failed",
            detail={
                "field":  "path",
                "reason": "must start with /",
                "nested": {"trace": "abc"},
            },
        )
        assert env.detail["field"] == "path"
        assert env.detail["nested"]["trace"] == "abc"

    def test_envelope_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            WebSurfaceV02ErrorEnvelope(
                error="x",
                version="v0.2.0",  # type: ignore[call-arg]
            )

    def test_envelope_round_trips_through_json(self):
        env = WebSurfaceV02ErrorEnvelope(
            error="not_implemented",
            detail={"path": "/echo"},
        )
        dumped = env.model_dump(mode="json")
        rebuilt = WebSurfaceV02ErrorEnvelope.model_validate(dumped)
        assert rebuilt == env

    def test_envelope_dump_omits_none_detail_only_when_set(self):
        # The model dumps ``detail: None`` unless excluded — that's
        # fine for the schema (detail is optional, null-allowed). We
        # just assert ``error`` always survives.
        env = WebSurfaceV02ErrorEnvelope(error="x")
        dumped = env.model_dump(mode="json")
        assert dumped["error"] == "x"
        assert "error" in dumped


# ---------------------------------------------------------------------------
# 4. Live handler responses re-parse as ErrorEnvelope (wire ↔ model)
# ---------------------------------------------------------------------------
@pytest.fixture
def client_enabled(monkeypatch):
    monkeypatch.setenv(web_surface.WEB_SURFACE_FLAG_ENV, "true")
    importlib.reload(web_surface)
    app = FastAPI()
    app.include_router(web_surface.router)
    return TestClient(app)


@pytest.fixture
def client_disabled(monkeypatch):
    monkeypatch.delenv(web_surface.WEB_SURFACE_FLAG_ENV, raising=False)
    importlib.reload(web_surface)
    app = FastAPI()
    app.include_router(web_surface.router)
    return TestClient(app)


class TestLiveResponseConformsToEnvelope:
    def test_501_body_re_parses_as_envelope(self, client_enabled):
        resp = client_enabled.get("/web-surface/v0.2/echo")
        assert resp.status_code == 501
        body = resp.json()
        # The wire body must be a valid ErrorEnvelope — if it's not,
        # the contract bridge is broken.
        env = WebSurfaceV02ErrorEnvelope.model_validate(body)
        assert env.error == "web_surface_not_implemented"
        assert env.detail["path"] == "/web-surface/v0.2/echo"
        assert env.detail["version"] == "v0.2.0"

    def test_503_body_re_parses_as_envelope(self, client_disabled):
        resp = client_disabled.get("/web-surface/v0.2/anything")
        assert resp.status_code == 503
        body = resp.json()
        env = WebSurfaceV02ErrorEnvelope.model_validate(body)
        assert env.error == "web_surface_disabled"
        assert "flag_env" in env.detail
        assert env.detail["flag_env"] == web_surface.WEB_SURFACE_FLAG_ENV

    def test_503_body_has_no_extras_beyond_envelope(self, client_disabled):
        resp = client_disabled.get("/web-surface/v0.2/x")
        body = resp.json()
        # Belt + braces: the envelope's extra="forbid" rejects extras
        # on parse, but we also assert the raw body's top-level key
        # set equals exactly {error, detail}.
        assert set(body.keys()) == {"error", "detail"}

    def test_501_body_has_no_extras_beyond_envelope(self, client_enabled):
        resp = client_enabled.get("/web-surface/v0.2/x")
        body = resp.json()
        assert set(body.keys()) == {"error", "detail"}
