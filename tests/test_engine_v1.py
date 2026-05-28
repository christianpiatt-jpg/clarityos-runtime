"""Tests for Card "Engine V1 Contract — Phase 1".

Covers the new POST /engine/v1/run umbrella endpoint, the
engine_v1.py pure-Python analytics it delegates to, and the
EngineResponseV1 Pydantic envelope.

Patterns mirrored from tests/test_v44_model_router.py:
  * reset_stores fixture for in-memory state
  * AppClient from conftest for ASGI-level requests
  * _make_user helper to mint sessions
"""
from __future__ import annotations

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


def _make_user(app_module, username, cohort="founder"):
    import bcrypt
    import users_store
    import sessions_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _basic_primitive(pressure=5.0, flow=4.0, resistance=2.0):
    return {
        "primitive_type": "signal",
        "domain":         "general",
        "pressure":       pressure,
        "flow":           flow,
        "resistance":     resistance,
    }


# ---------------------------------------------------------------------------
# engine_v1.py — pure-Python analytics
# ---------------------------------------------------------------------------
def test_engine_v1_compute_overlay_classifies_regime(reset_stores):
    import engine_v1
    prim = engine_v1.build_primitive(_basic_primitive(pressure=1.0, flow=1.0, resistance=10.0))
    overlay = engine_v1.compute_overlay(prim)
    assert overlay["flow_regime"] == "laminar"
    assert overlay["stability"] == pytest.approx(0.9)
    assert overlay["reynolds_number"] >= 0
    assert overlay["resilience"] >= 0


def test_engine_v1_compute_overlay_marks_critical_zone(reset_stores):
    """Pressure inside the Godhard critical zone (3.5 < p < 6.5) → in_critical_zone=True."""
    import engine_v1
    prim = engine_v1.build_primitive(_basic_primitive(pressure=5.0))
    overlay = engine_v1.compute_overlay(prim)
    assert overlay["in_critical_zone"] is True
    assert overlay["distance_to_fold"] == pytest.approx(0.0, abs=1e-6)


def test_engine_v1_project_forward_records_trajectories(reset_stores):
    import engine_v1
    prim = engine_v1.build_primitive(_basic_primitive(pressure=8.0, flow=6.0, resistance=2.0))
    proj = engine_v1.project_forward(prim, days=10)
    assert proj["projection_days"] == 10
    assert len(proj["pressure_trajectory"]) == 11  # day 0..10
    assert len(proj["flow_trajectory"]) == 11
    assert proj["pressure_trajectory"][0] == pytest.approx(8.0)
    # Decay is monotonic-non-increasing.
    for i in range(len(proj["pressure_trajectory"]) - 1):
        assert proj["pressure_trajectory"][i + 1] <= proj["pressure_trajectory"][i] + 1e-9


def test_engine_v1_project_forward_rejects_negative_days(reset_stores):
    import engine_v1
    prim = engine_v1.build_primitive(_basic_primitive())
    with pytest.raises(ValueError):
        engine_v1.project_forward(prim, days=-1)


def test_engine_v1_regress_to_origin_builds_path(reset_stores):
    import engine_v1
    prim = engine_v1.build_primitive(_basic_primitive(pressure=6.0))
    reg = engine_v1.regress_to_origin(prim)
    assert reg["primitive_id"] == prim["metadata"]["primitive_id"]
    assert len(reg["path"]) == 21  # 20 steps + endpoint
    assert reg["origin_state"]["hydraulic_state"]["pressure"] <= prim["hydraulic_state"]["pressure"]


# ---------------------------------------------------------------------------
# /engine/v1/run — happy path + shape
# ---------------------------------------------------------------------------
def test_engine_v1_endpoint_happy_path(app_module, client):
    user, sid = _make_user(app_module, "ev1_basic", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={"primitives": [_basic_primitive(pressure=5.0)], "projection_days": 7},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert len(body["primitives"]) == 1
    assert len(body["overlays"]) == 1
    assert body["regression"] is not None
    assert body["projection"] is not None
    assert body["projection"]["projection_days"] == 7
    assert body["diagnostics"]["observation_id"].startswith("obs_")
    # Phase-2 / Phase-3 fields default to None on the wire.
    assert body.get("validation") is None
    assert body.get("cross_regression") is None
    assert body.get("backtest") is None


def test_engine_v1_endpoint_empty_primitives_nulls_regression(app_module, client):
    user, sid = _make_user(app_module, "ev1_empty", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={"primitives": [], "projection_days": 30},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["primitives"] == []
    assert body["overlays"] == []
    assert body["regression"] is None
    assert body["projection"] is None
    # Diagnostics still emitted even with no inputs.
    assert "observation_id" in body["diagnostics"]


def test_engine_v1_endpoint_requires_session(app_module, client):
    r = client.post(
        "/engine/v1/run",
        json={"primitives": [_basic_primitive()]},
    )
    assert r.status_code == 401


def test_engine_v1_endpoint_rate_limit_enforced(app_module, client, monkeypatch):
    """30/min cap; with enforcement on, the 31st call returns 429."""
    import v29_hardening
    monkeypatch.setattr(v29_hardening, "_RATE_ENFORCE", True)
    user, sid = _make_user(app_module, "ev1_rl", cohort=None)
    last_status = 200
    body_json: dict = {}
    for i in range(31):
        r = client.post(
            "/engine/v1/run", headers=_auth(sid),
            json={"primitives": [_basic_primitive()]},
        )
        last_status = r.status_code
        if last_status == 429:
            body_json = r.json()
            break
    assert last_status == 429
    assert body_json.get("error") == "rate_limited"


def test_engine_v1_endpoint_multiple_primitives_one_overlay_each(app_module, client):
    user, sid = _make_user(app_module, "ev1_multi", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={
            "primitives": [
                _basic_primitive(pressure=1.0, flow=1.0, resistance=10.0),  # laminar
                _basic_primitive(pressure=8.0, flow=8.0, resistance=0.5),   # turbulent
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["overlays"]) == 2
    regimes = {o["flow_regime"] for o in body["overlays"]}
    assert "laminar" in regimes
    assert "turbulent" in regimes
    # Regression/projection still anchor on the first primitive.
    assert body["regression"]["primitive_id"] == body["primitives"][0]["metadata"]["primitive_id"]


def test_engine_v1_endpoint_shape_validates_against_pydantic(app_module, client):
    """Wire response must round-trip through EngineResponseV1.model_validate."""
    from app import EngineResponseV1
    user, sid = _make_user(app_module, "ev1_shape", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={"primitives": [_basic_primitive()]},
    )
    assert r.status_code == 200
    parsed = EngineResponseV1.model_validate(r.json())
    assert parsed.diagnostics.observer_notes  # non-empty
    assert parsed.overlays[0].flow_regime in {"laminar", "transitional", "turbulent"}


def test_engine_v1_card20_cherrypick_fields_present(app_module, client):
    """Card 20 cherry-pick: metadata lineage, primitive self-refs,
    Godhard overlay fields, diagnostics.interventions all land in the
    response with their documented Phase-1 defaults / computed values."""
    user, sid = _make_user(app_module, "ev1_cp", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={"primitives": [_basic_primitive(pressure=5.0, flow=4.0, resistance=2.0)]},
    )
    assert r.status_code == 200
    body = r.json()

    # 1. EnginePrimitiveMetadata lineage fields exist + default empty.
    meta = body["primitives"][0]["metadata"]
    assert meta["ancestors"]  == []
    assert meta["depends_on"] == []
    assert meta["influences"] == []

    # 2. EnginePrimitive recursive fields exist + default None / [].
    prim = body["primitives"][0]
    assert prim["origin_state"] is None
    assert prim["historical_states"] == []

    # 3. EngineOverlayResult Godhard fields populated.
    overlay = body["overlays"][0]
    for field in ("curve_position", "on_upper_branch", "sensitivity", "hysteresis"):
        assert field in overlay, f"overlay missing {field}"
    # At pressure=5.0 (critical centre): in_critical_zone=True,
    # sensitivity peaks at 1 + 2*1.5 = 4.0, on_upper_branch=False
    # (pressure == GODHARD_CENTER, strictly greater is False).
    assert overlay["curve_position"]  == 5.0
    assert overlay["on_upper_branch"] is False
    assert overlay["sensitivity"]     == 4.0
    assert overlay["hysteresis"]      == 3.0  # GODHARD_HALF_WIDTH * 2

    # 4. EngineDiagnostics.interventions exists + default [].
    assert body["diagnostics"]["interventions"] == []


def test_engine_v1_card20_overlay_upper_branch_above_center(app_module, client):
    """pressure > GODHARD_CENTER (5.0) → on_upper_branch=True."""
    user, sid = _make_user(app_module, "ev1_cp_upper", cohort=None)
    r = client.post(
        "/engine/v1/run", headers=_auth(sid),
        json={"primitives": [_basic_primitive(pressure=7.0, flow=4.0, resistance=2.0)]},
    )
    assert r.status_code == 200
    overlay = r.json()["overlays"][0]
    assert overlay["on_upper_branch"] is True
    # Outside the critical zone (distance=2.0 > HALF_WIDTH=1.5) →
    # sensitivity collapses to baseline 1.0.
    assert overlay["sensitivity"] == 1.0


def test_engine_v1_endpoint_determinism_for_same_input(app_module, client):
    """Same input → same overlays + projection. (Observation ids and
    timestamps differ across calls — exclude those from comparison.)"""
    user, sid = _make_user(app_module, "ev1_det", cohort=None)
    body = {"primitives": [_basic_primitive(pressure=6.0, flow=3.0, resistance=2.0)]}

    r1 = client.post("/engine/v1/run", headers=_auth(sid), json=body)
    r2 = client.post("/engine/v1/run", headers=_auth(sid), json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    j1, j2 = r1.json(), r2.json()

    # Overlay payloads are deterministic functions of the primitive's
    # hydraulic state — they should match modulo the primitive_id.
    o1 = {**j1["overlays"][0], "primitive_id": "_"}
    o2 = {**j2["overlays"][0], "primitive_id": "_"}
    assert o1 == o2

    # Projection trajectories likewise depend only on hydraulic state.
    assert j1["projection"]["pressure_trajectory"] == j2["projection"]["pressure_trajectory"]
    assert j1["projection"]["flow_trajectory"]     == j2["projection"]["flow_trajectory"]
