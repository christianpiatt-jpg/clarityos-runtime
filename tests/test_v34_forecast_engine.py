"""
Tests for v34 — ELINS Forecast Engine (multi-primitive envelopes).

Covers:
* forecast_engine.compute_envelope — single primitive (formula + days)
* forecast_engine.compute_multi_envelope — magnitude-weighted normalization
* forecast_engine.compute_domain_envelope — domain-vector weighting
* forecast_engine.compute_chain_envelope — attenuation propagation
* determinism — same input → same output
* compute_forecast_block + ELINS integration — generate_ELINS embeds
  ``forecast_engine`` and the block has the right shape.
* Endpoints: POST /elins/forecast, GET /elins/forecast/example,
  POST /founder/elins/forecast/run + auth + validation.
* UI API shape — every chart component reads from a stable, top-level
  shape (primitive_envelopes, multi_envelope, domain_envelopes,
  chain, chain_envelope, days, version).
"""
from __future__ import annotations

import math
import time

import pytest


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------
def test_compute_envelope_basic_formula(reset_stores):
    from ELINS import forecast_engine as fe
    out = fe.compute_envelope({"key": "pressure", "intensity": 1.0, "lambda": 0.5}, days=3)
    # Length = days+1 → D+0..D+3
    assert len(out) == 4
    # ep(D+0) == intensity
    assert out[0] == pytest.approx(1.0, abs=1e-6)
    # ep(D+n) == ep0 * exp(-lambda * n)
    for n, v in enumerate(out):
        assert v == pytest.approx(math.exp(-0.5 * n), abs=1e-6)


def test_compute_envelope_uses_default_lambda_when_omitted(reset_stores):
    from ELINS import forecast_engine as fe
    out = fe.compute_envelope({"key": "pressure", "intensity": 0.8}, days=5)
    # Default lambda for "pressure" is 0.20 — so ep(D+5) ≈ 0.8 * exp(-1.0)
    assert out[5] == pytest.approx(0.8 * math.exp(-1.0), abs=1e-6)
    # Length matches
    assert len(out) == 6


def test_compute_envelope_validates(reset_stores):
    from ELINS import forecast_engine as fe
    with pytest.raises(ValueError):
        fe.compute_envelope("not a dict", days=5)
    with pytest.raises(ValueError):
        fe.compute_envelope({"intensity": 0.5}, days=5)
    with pytest.raises(ValueError):
        fe.compute_envelope({"key": "x", "intensity": 0.5}, days=0)
    with pytest.raises(ValueError):
        fe.compute_envelope({"key": "x", "intensity": 0.5, "lambda": -0.1}, days=5)


# ---------------------------------------------------------------------------
# Multi-primitive envelope
# ---------------------------------------------------------------------------
def test_compute_multi_envelope_magnitude_weighted(reset_stores):
    from ELINS import forecast_engine as fe
    primitives = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.0},
        {"key": "trust",    "intensity": 0.5, "lambda": 0.0},
    ]
    # With lambda=0 there's no decay; magnitude-weighted average is:
    # (1.0*1.0 + 0.5*0.5) / (1.0 + 0.5) = 1.25 / 1.5 ≈ 0.8333
    out = fe.compute_multi_envelope(primitives, days=3)
    assert len(out) == 4
    for v in out:
        assert v == pytest.approx(1.25 / 1.5, abs=1e-6)


def test_compute_multi_envelope_decays(reset_stores):
    from ELINS import forecast_engine as fe
    primitives = [
        {"key": "pressure", "intensity": 1.0, "lambda": 1.0},
    ]
    out = fe.compute_multi_envelope(primitives, days=3)
    # Single-element multi-envelope reduces to a single-primitive envelope.
    for n, v in enumerate(out):
        assert v == pytest.approx(math.exp(-n), abs=1e-6)


def test_compute_multi_envelope_zero_magnitude_returns_zero(reset_stores):
    from ELINS import forecast_engine as fe
    out = fe.compute_multi_envelope(
        [{"key": "pressure", "intensity": 0.0}, {"key": "trust", "intensity": 0.0}],
        days=2,
    )
    assert out == [0.0, 0.0, 0.0]


def test_compute_multi_envelope_validates(reset_stores):
    from ELINS import forecast_engine as fe
    with pytest.raises(ValueError):
        fe.compute_multi_envelope("not a list", days=3)


# ---------------------------------------------------------------------------
# Domain envelope
# ---------------------------------------------------------------------------
def test_compute_domain_envelope_weights_primitives(reset_stores):
    from ELINS import forecast_engine as fe
    primitives = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.0},
        {"key": "trust",    "intensity": 1.0, "lambda": 0.0},
    ]
    # Vector that fully weights pressure → result == pressure intensity
    only_pressure = {"pressure": 1.0, "trust": 0.0}
    out = fe.compute_domain_envelope(only_pressure, primitives, days=2)
    for v in out:
        assert v == pytest.approx(1.0, abs=1e-6)
    # Vector that fully weights trust → result == trust intensity
    only_trust = {"pressure": 0.0, "trust": 1.0}
    out2 = fe.compute_domain_envelope(only_trust, primitives, days=2)
    for v in out2:
        assert v == pytest.approx(1.0, abs=1e-6)
    # 50/50 → average
    half = {"pressure": 0.5, "trust": 0.5}
    out3 = fe.compute_domain_envelope(half, primitives, days=2)
    for v in out3:
        assert v == pytest.approx(1.0, abs=1e-6)


def test_compute_domain_envelope_decays(reset_stores):
    from ELINS import forecast_engine as fe
    primitives = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.5},
    ]
    out = fe.compute_domain_envelope({"pressure": 1.0}, primitives, days=4)
    for n, v in enumerate(out):
        assert v == pytest.approx(math.exp(-0.5 * n), abs=1e-6)


def test_compute_domain_envelope_zero_weight_returns_zero(reset_stores):
    from ELINS import forecast_engine as fe
    out = fe.compute_domain_envelope(
        {},
        [{"key": "pressure", "intensity": 0.7}],
        days=3,
    )
    assert out == [0.0, 0.0, 0.0, 0.0]


def test_compute_domain_envelope_rejects_negative_weight(reset_stores):
    from ELINS import forecast_engine as fe
    with pytest.raises(ValueError):
        fe.compute_domain_envelope(
            {"pressure": -0.5},
            [{"key": "pressure", "intensity": 0.5}],
            days=3,
        )


# ---------------------------------------------------------------------------
# Chain envelope
# ---------------------------------------------------------------------------
def test_compute_chain_envelope_applies_attenuation(reset_stores):
    from ELINS import forecast_engine as fe
    chain = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.0, "attenuation": 1.0},
        {"key": "tension",  "intensity": 1.0, "lambda": 0.0, "attenuation": 0.5},
    ]
    out = fe.compute_chain_envelope(chain, days=2)
    # No decay (lambda=0); per-day = sum(att * intensity) = 1.0 + 0.5 = 1.5
    for v in out:
        assert v == pytest.approx(1.5, abs=1e-6)


def test_compute_chain_envelope_default_attenuation_is_decreasing(reset_stores):
    from ELINS import forecast_engine as fe
    chain = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.0},
        {"key": "tension",  "intensity": 1.0, "lambda": 0.0},
        {"key": "drift",    "intensity": 1.0, "lambda": 0.0},
    ]
    out = fe.compute_chain_envelope(chain, days=1)
    # Default attenuation tuple starts at (1.0, 0.8, 0.65, ...).
    # With lambda=0 each link contributes attenuation * intensity.
    expected = 1.0 + 0.8 + 0.65
    for v in out:
        assert v == pytest.approx(expected, abs=1e-6)


def test_compute_chain_envelope_decay_propagates(reset_stores):
    from ELINS import forecast_engine as fe
    chain = [
        {"key": "pressure", "intensity": 1.0, "lambda": 0.5, "attenuation": 1.0},
    ]
    out = fe.compute_chain_envelope(chain, days=3)
    for n, v in enumerate(out):
        assert v == pytest.approx(math.exp(-0.5 * n), abs=1e-6)


def test_compute_chain_envelope_rejects_empty(reset_stores):
    from ELINS import forecast_engine as fe
    with pytest.raises(ValueError):
        fe.compute_chain_envelope([], days=3)
    with pytest.raises(ValueError):
        fe.compute_chain_envelope("not a list", days=3)


def test_compute_chain_envelope_rejects_negative_attenuation(reset_stores):
    from ELINS import forecast_engine as fe
    with pytest.raises(ValueError):
        fe.compute_chain_envelope(
            [{"key": "pressure", "intensity": 1.0, "attenuation": -0.1}],
            days=3,
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_forecast_engine_is_deterministic(reset_stores):
    from ELINS import forecast_engine as fe
    intensities = {
        "pressure": 0.85, "tension": 0.6, "trust": 0.2,
        "drift": 0.45, "contradiction": 0.5, "alignment": 0.15,
    }
    edges = [
        {"from": "pressure", "to": "tension", "weight": 0.6},
        {"from": "tension", "to": "drift", "weight": 0.45},
    ]
    a = fe.compute_forecast_block(intensities, edges=edges, days=5)
    b = fe.compute_forecast_block(intensities, edges=edges, days=5)
    assert a == b


def test_compute_envelope_deterministic(reset_stores):
    from ELINS import forecast_engine as fe
    p = {"key": "drift", "intensity": 0.4, "lambda": 0.07}
    a = fe.compute_envelope(p, days=5)
    b = fe.compute_envelope(p, days=5)
    assert a == b


# ---------------------------------------------------------------------------
# Integration with generate_ELINS
# ---------------------------------------------------------------------------
def test_generate_ELINS_includes_forecast_engine(reset_stores):
    from ELINS import standard_elins as se
    out = se.generate_ELINS(
        "the institution is drifting under enormous pressure with rising "
        "tension and contradiction at every level."
    )
    assert "forecast_engine" in out
    fe_block = out["forecast_engine"]
    # required keys
    for k in ("primitive_envelopes", "multi_envelope", "domain_envelopes",
              "chain", "chain_envelope", "days", "version"):
        assert k in fe_block, f"missing forecast_engine.{k}"
    # primitive_envelopes are arrays of length days+1
    n = fe_block["days"]
    assert n == 5
    for key, vals in fe_block["primitive_envelopes"].items():
        assert isinstance(vals, list) and len(vals) == n + 1, key
    assert isinstance(fe_block["multi_envelope"], list)
    assert len(fe_block["multi_envelope"]) == n + 1
    # domain_envelopes covers all spec-named domains
    from ELINS.forecast_engine import DOMAIN_NAMES
    for name in DOMAIN_NAMES:
        assert name in fe_block["domain_envelopes"]
        assert len(fe_block["domain_envelopes"][name]) == n + 1


def test_generate_ELINS_forecast_engine_deterministic(reset_stores):
    from ELINS import standard_elins as se
    text = "tariffs are creating pressure and trust between partners is eroding."
    a = se.generate_ELINS(text)
    b = se.generate_ELINS(text)
    assert a["forecast_engine"] == b["forecast_engine"]


def test_generate_ELINS_chain_present_when_edges_exist(reset_stores):
    from ELINS import standard_elins as se
    out = se.generate_ELINS(
        "Pressure breeds tension; tension causes drift; drift fuels contradiction."
    )
    assert out["causal_chain"]["edge_count"] > 0
    chain = out["forecast_engine"]["chain"]
    chain_env = out["forecast_engine"]["chain_envelope"]
    if chain is not None:
        assert isinstance(chain, list) and len(chain) >= 2
        assert isinstance(chain_env, list)
        assert len(chain_env) == out["forecast_engine"]["days"] + 1


# ---------------------------------------------------------------------------
# Endpoint tests
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
    import secrets
    import users_store, sessions_store, bcrypt
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


def test_endpoint_elins_forecast_returns_block(app_module, client):
    user, sid = _make_user(app_module, "fp_a", cohort="founder")
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={
            "primitives": [
                {"key": "pressure", "intensity": 0.8},
                {"key": "tension",  "intensity": 0.5},
                {"key": "trust",    "intensity": 0.3},
            ],
            "days": 5,
        },
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    fe_block = body["forecast"]
    assert "primitive_envelopes" in fe_block
    assert "multi_envelope" in fe_block
    assert "domain_envelopes" in fe_block
    assert fe_block["days"] == 5
    # default = all 7 spec domains
    assert len(fe_block["domain_envelopes"]) == 7


def test_endpoint_elins_forecast_with_chain(app_module, client):
    user, sid = _make_user(app_module, "fp_b", cohort="founder")
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={
            "primitives": [
                {"key": "pressure", "intensity": 0.9},
                {"key": "tension",  "intensity": 0.6},
            ],
            "chain": [
                {"key": "pressure", "intensity": 0.9, "attenuation": 1.0},
                {"key": "tension",  "intensity": 0.6, "attenuation": 0.7},
            ],
            "days": 4,
        },
    )
    assert r.status_code == 200, r.json()
    fe_block = r.json()["forecast"]
    assert fe_block["days"] == 4
    assert isinstance(fe_block["chain_envelope"], list)
    assert len(fe_block["chain_envelope"]) == 5  # days+1


def test_endpoint_elins_forecast_with_domain_subset(app_module, client):
    user, sid = _make_user(app_module, "fp_c", cohort="founder")
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={
            "primitives": [{"key": "pressure", "intensity": 0.8}],
            "domains": ["Geopolitical", "Economic_Markets"],
            "days": 3,
        },
    )
    assert r.status_code == 200
    fe_block = r.json()["forecast"]
    assert set(fe_block["domain_envelopes"].keys()) == {"Geopolitical", "Economic_Markets"}


def test_endpoint_elins_forecast_rejects_bad_domain(app_module, client):
    user, sid = _make_user(app_module, "fp_d", cohort="founder")
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={
            "primitives": [{"key": "pressure", "intensity": 0.5}],
            "domains": ["NotARealDomain"],
        },
    )
    assert r.status_code == 400


def test_endpoint_elins_forecast_rejects_empty_primitives(app_module, client):
    user, sid = _make_user(app_module, "fp_e", cohort="founder")
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={"primitives": []},
    )
    assert r.status_code == 400


def test_endpoint_elins_forecast_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "fp_lurker", cohort=None)
    r = client.post(
        "/elins/forecast", headers=_auth(sid),
        json={"primitives": [{"key": "pressure", "intensity": 0.5}]},
    )
    assert r.status_code == 403


def test_endpoint_elins_forecast_example_public(app_module, client):
    r = client.get("/elins/forecast/example")
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    ex = body["example"]
    assert "label" in ex and "inputs" in ex and "forecast" in ex
    fe_block = ex["forecast"]
    assert "primitive_envelopes" in fe_block
    assert "multi_envelope" in fe_block
    assert "domain_envelopes" in fe_block
    assert fe_block["days"] >= 1


def test_endpoint_founder_elins_forecast_run_persists(app_module, client):
    from ELINS import elins_project as ep
    user, sid = _make_user(app_module, "fp_founder", cohort="founder")
    r = client.post(
        "/founder/elins/forecast/run", headers=_auth(sid),
        json={"text": "Court ruling on constitutional pressure", "days": 5},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "forecast_engine" in body["elins"]
    runs = ep.list_runs_for_user("fp_founder")
    assert any(row["id"] == body["run_id"] for row in runs)


def test_endpoint_founder_elins_forecast_run_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fp_outsider", cohort=None)
    r = client.post(
        "/founder/elins/forecast/run", headers=_auth(sid),
        json={"text": "x x x x"},
    )
    assert r.status_code == 403


def test_endpoint_founder_elins_forecast_run_custom_days(app_module, client):
    user, sid = _make_user(app_module, "fp_days", cohort="founder")
    r = client.post(
        "/founder/elins/forecast/run", headers=_auth(sid),
        json={"text": "tension under sustained pressure", "days": 10},
    )
    assert r.status_code == 200, r.json()
    fe_block = r.json()["elins"]["forecast_engine"]
    assert fe_block["days"] == 10
    assert len(fe_block["multi_envelope"]) == 11


# ---------------------------------------------------------------------------
# UI API shape — every chart component reads these stable keys.
# ---------------------------------------------------------------------------
def test_ui_api_shape_is_stable(app_module, client):
    """Locks the keys the web + phone chart components rely on."""
    r = client.get("/elins/forecast/example")
    assert r.status_code == 200
    fe_block = r.json()["example"]["forecast"]
    expected_top_level = {
        "primitive_envelopes", "multi_envelope", "domain_envelopes",
        "chain", "chain_envelope", "days", "version",
    }
    assert expected_top_level.issubset(set(fe_block.keys()))
    # primitive_envelopes is a dict of arrays
    for k, v in fe_block["primitive_envelopes"].items():
        assert isinstance(k, str)
        assert isinstance(v, list)
        for x in v:
            assert isinstance(x, (int, float))
    # multi_envelope is a flat array
    assert isinstance(fe_block["multi_envelope"], list)
    # domain_envelopes is keyed by spec-name domain
    from ELINS.forecast_engine import DOMAIN_NAMES
    for name in DOMAIN_NAMES:
        assert name in fe_block["domain_envelopes"]
    # chain (if present) has key/intensity/attenuation
    if fe_block["chain"]:
        for link in fe_block["chain"]:
            assert "key" in link
            assert "intensity" in link
