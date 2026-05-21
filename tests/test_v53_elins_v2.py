"""
Tests for v53 — ELINS v2 view adapter (Path C).

Covers each of the six analytical heads in isolation, the orchestrator
``build_v2_envelope``, the kernel function ``run_elins_v2``, and the
``POST /elins/v2/run`` endpoint.

Architecture invariant tests:
  * No new model calls (route_request not touched)
  * No imports from /skills_export/
  * Existing v33-v37 surfaces still emit unchanged outputs
"""
from __future__ import annotations

import math
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
    import sessions_store
    import users_store
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


# ===========================================================================
# §1 — ETF
# ===========================================================================
def test_etf_zero_intensity_returns_zero():
    from ELINS import elins_v2_view as v
    assert v.compute_etf(0.0, 0, 365) == 0.0
    assert v.compute_etf(0.0, 5, 18250) == 0.0


def test_etf_decays_over_horizons():
    """At ep0=0.7, edge_count=2: 365d ≈ 0.46, 3650d ≈ 0.01, 18250d ≈ 0."""
    from ELINS import elins_v2_view as v
    e365   = v.compute_etf(0.7, 2, 365)
    e3650  = v.compute_etf(0.7, 2, 3650)
    e18250 = v.compute_etf(0.7, 2, 18250)
    assert 0.40 < e365 < 0.52    # ~0.46
    assert 0.005 < e3650 < 0.025  # ~0.01
    assert e18250 < 0.01
    # Monotone decreasing over time.
    assert e365 > e3650 > e18250


def test_etf_higher_edge_count_means_slower_decay():
    """More incident causal edges → λ_eff lower → more intensity survives."""
    from ELINS import elins_v2_view as v
    decayed_with_edges    = v.compute_etf(0.6, 5, 365)
    decayed_without_edges = v.compute_etf(0.6, 0, 365)
    assert decayed_with_edges > decayed_without_edges


def test_etf_higher_ep0_means_faster_decay_rate():
    """At equal edge_count, higher ep0 has steeper relative decay
    (α boosts λ_eff with ep0). Compare survival fraction."""
    from ELINS import elins_v2_view as v
    ratio_high = v.compute_etf(0.9, 0, 1000) / 0.9
    ratio_low  = v.compute_etf(0.2, 0, 1000) / 0.2
    assert ratio_high < ratio_low


def test_etf_lambda_clamp_prevents_pathological_values():
    """Even with very high ep0 + zero edges, λ stays bounded.
    With ep0=1.0, edges=0: raw λ = 0.001·(1+0.5) = 0.0015 → within clamp.
    With ep0=0.0, edges=20: raw λ = 0.001·(1-2) = -0.001 → clamped to 1e-4."""
    from ELINS import elins_v2_view as v
    # ep0=1.0, no edges → λ ≈ 0.0015 (within clamp; survival > exp(-0.0015·365))
    e_low_load = v.compute_etf(1.0, 0, 365)
    assert e_low_load > 1.0 * math.exp(-0.002 * 365)
    # Very negative raw λ scenario via many edges — should not increase intensity
    e_many_edges = v.compute_etf(0.5, 50, 365)
    assert e_many_edges <= 0.5  # never exceeds ep0


# ===========================================================================
# §2 — State distribution + attractor
# ===========================================================================
def test_state_distribution_sums_to_one():
    from ELINS import elins_v2_view as v
    intensities = {
        "pressure": 0.5, "tension": 0.4, "trust": 0.6,
        "drift": 0.3, "contradiction": 0.2, "alignment": 0.5,
    }
    dist, _ = v.compute_state_distribution(intensities)
    total = sum(dist.values())
    assert abs(total - 1.0) < 1e-3


def test_state_distribution_keys_are_S1_through_S4():
    from ELINS import elins_v2_view as v
    dist, _ = v.compute_state_distribution({})
    assert set(dist.keys()) == {"S1", "S2", "S3", "S4"}


def test_attractor_S1_for_calm_field():
    """Low pressure, high alignment, high trust → S1 (stable coherence)."""
    from ELINS import elins_v2_view as v
    intensities = {
        "pressure": 0.1, "tension": 0.1, "trust": 0.8,
        "drift": 0.05, "contradiction": 0.05, "alignment": 0.8,
    }
    dist, attractor = v.compute_state_distribution(intensities)
    assert attractor == "S1", dist


def test_attractor_S4_for_collapse_profile():
    """For S4 to dominate S3, the (drift × contradiction) kicker must
    exceed (1 − trust). Tune the profile accordingly."""
    from ELINS import elins_v2_view as v
    # raw_S3 = p·(1-al)·(1-tr) = 0.95·0.95·0.4 = 0.361
    # raw_S4 = p·dr·(1-al)·cn = 0.95·1.0·0.95·1.0 = 0.902 > S3
    intensities = {
        "pressure": 0.95, "tension": 0.7, "trust": 0.6,
        "drift": 1.0, "contradiction": 1.0, "alignment": 0.05,
    }
    dist, attractor = v.compute_state_distribution(intensities)
    assert attractor == "S4", dist


def test_state_distribution_handles_missing_keys():
    from ELINS import elins_v2_view as v
    dist, attractor = v.compute_state_distribution({"pressure": 0.5})
    assert sum(dist.values()) == pytest.approx(1.0, abs=1e-3)
    assert attractor in {"S1", "S2", "S3", "S4"}


# ===========================================================================
# §3 — Collapse state
# ===========================================================================
def test_collapse_state_hard_when_S4_above_threshold():
    from ELINS import elins_v2_view as v
    result = v.compute_collapse_state(
        {"S1": 0.1, "S2": 0.2, "S3": 0.2, "S4": 0.5},
        {"intensity_mean": 0.5},
        {"primitive_envelopes": {"pressure": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3]}},
        {"intensities": {"pressure": 0.3}},
    )
    assert result == "hard"


def test_collapse_state_soft_when_S4_in_middle_band():
    from ELINS import elins_v2_view as v
    result = v.compute_collapse_state(
        {"S1": 0.2, "S2": 0.3, "S3": 0.2, "S4": 0.3},
        {"intensity_mean": 0.4},
        {"primitive_envelopes": {"pressure": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3]}},
        {"intensities": {"pressure": 0.3}},
    )
    assert result == "soft"


def test_collapse_state_soft_via_field_intensity_fallback():
    """Low S4 mass, but high field_intensity + rising pressure → soft."""
    from ELINS import elins_v2_view as v
    result = v.compute_collapse_state(
        {"S1": 0.4, "S2": 0.3, "S3": 0.2, "S4": 0.1},
        {"intensity_mean": 0.75},
        {"primitive_envelopes": {"pressure": [0.4, 0.45, 0.5, 0.52, 0.55, 0.6]}},
        {"intensities": {"pressure": 0.4}},
    )
    assert result == "soft"


def test_collapse_state_none_default():
    """Low S4, moderate field, no rising pressure → none."""
    from ELINS import elins_v2_view as v
    result = v.compute_collapse_state(
        {"S1": 0.5, "S2": 0.3, "S3": 0.15, "S4": 0.05},
        {"intensity_mean": 0.4},
        {"primitive_envelopes": {"pressure": [0.3, 0.28, 0.26, 0.24, 0.22, 0.20]}},
        {"intensities": {"pressure": 0.3}},
    )
    assert result == "none"


# ===========================================================================
# §4 — P0-P8 distribution
# ===========================================================================
def test_p0_p8_sums_to_one():
    from ELINS import elins_v2_view as v
    out = v.compute_p0_p8(
        {"S1": 0.4, "S2": 0.3, "S3": 0.2, "S4": 0.1},
        "none",
        0.5, 0.2,
    )
    total = sum(out.values())
    assert abs(total - 1.0) < 1e-3, out


def test_p0_p8_has_all_nine_keys():
    from ELINS import elins_v2_view as v
    out = v.compute_p0_p8(
        {"S1": 0.4, "S2": 0.3, "S3": 0.2, "S4": 0.1},
        "none", 0.5, 0.2,
    )
    assert set(out.keys()) == {f"P{i}" for i in range(9)}


def test_p0_p8_peaceful_dominates_for_calm_state_distribution():
    """S1+S2 heavy → peaceful row (P0+P1+P2) > others."""
    from ELINS import elins_v2_view as v
    out = v.compute_p0_p8(
        {"S1": 0.6, "S2": 0.3, "S3": 0.05, "S4": 0.05},
        "none", 0.5, 0.2,
    )
    peaceful = out["P0"] + out["P1"] + out["P2"]
    contested = out["P3"] + out["P4"] + out["P5"]
    ruptured = out["P6"] + out["P7"] + out["P8"]
    assert peaceful > contested
    assert peaceful > ruptured


def test_p0_p8_ruptured_grows_with_hard_collapse():
    """Same state_distribution, but collapse=hard → ruptured mass increases."""
    from ELINS import elins_v2_view as v
    sd = {"S1": 0.3, "S2": 0.3, "S3": 0.2, "S4": 0.2}
    none_out = v.compute_p0_p8(sd, "none", 0.5, 0.2)
    hard_out = v.compute_p0_p8(sd, "hard", 0.5, 0.2)
    none_ruptured = none_out["P6"] + none_out["P7"] + none_out["P8"]
    hard_ruptured = hard_out["P6"] + hard_out["P7"] + hard_out["P8"]
    assert hard_ruptured > none_ruptured


# ===========================================================================
# §5 — Geography tier
# ===========================================================================
def test_geography_tier_none_when_no_regional_object():
    from ELINS import elins_v2_view as v
    assert v.compute_geography_tier(None) is None
    assert v.compute_geography_tier({}) is None


def test_geography_tier_T1_anchor():
    """Low field + high trust + high alignment + low drift → T1."""
    from ELINS import elins_v2_view as v
    regional = {
        "ep_field_summary": {"intensity_mean": 0.2},
        "primitives": {"intensities": {
            "trust": 0.9, "alignment": 0.9, "drift": 0.05,
        }},
    }
    assert v.compute_geography_tier(regional) == "T1"


def test_geography_tier_T4_exposed():
    """High field + low trust + low alignment + high drift → T4."""
    from ELINS import elins_v2_view as v
    regional = {
        "ep_field_summary": {"intensity_mean": 0.9},
        "primitives": {"intensities": {
            "trust": 0.1, "alignment": 0.1, "drift": 0.8,
        }},
    }
    assert v.compute_geography_tier(regional) == "T4"


def test_geography_tier_boundaries_are_inclusive_at_lower_bound():
    """tier_score == 1.20 → T1 (≥); tier_score just under → T2."""
    from ELINS import elins_v2_view as v
    # Construct intensities so (1-f)·t + a - d = 1.20 exactly:
    # field=0, trust=0.6, alignment=0.6, drift=0 → score = 0.6 + 0.6 - 0 = 1.20
    regional = {
        "ep_field_summary": {"intensity_mean": 0.0},
        "primitives": {"intensities": {
            "trust": 0.6, "alignment": 0.6, "drift": 0.0,
        }},
    }
    assert v.compute_geography_tier(regional) == "T1"


# ===========================================================================
# §6 — Multiplier
# ===========================================================================
def test_multiplier_minimum_at_idle():
    from ELINS import elins_v2_view as v
    assert v.compute_multiplier(0.0, 0.0, "none") == 1.0


def test_multiplier_maximum_clamped_at_2():
    """Even with all inputs maxed, multiplier never exceeds 2.0."""
    from ELINS import elins_v2_view as v
    assert v.compute_multiplier(1.0, 1.0, "hard") <= 2.0


def test_multiplier_amplifies_with_collapse_state():
    """Same field/S4, harder collapse → higher multiplier."""
    from ELINS import elins_v2_view as v
    none = v.compute_multiplier(0.5, 0.2, "none")
    soft = v.compute_multiplier(0.5, 0.2, "soft")
    hard = v.compute_multiplier(0.5, 0.2, "hard")
    assert none < soft < hard


def test_multiplier_amplifies_with_field_intensity():
    from ELINS import elins_v2_view as v
    low  = v.compute_multiplier(0.1, 0.0, "none")
    high = v.compute_multiplier(0.9, 0.0, "none")
    assert high > low


# ===========================================================================
# build_v2_envelope orchestrator
# ===========================================================================
def test_build_v2_envelope_full_shape(reset_stores):
    """Smoke test: round-trip a real ELINS run through the adapter
    and confirm the v2 envelope has every key the spec requires."""
    from ELINS import elins_v2_view as v
    from ELINS import standard_elins
    elins = standard_elins.generate_ELINS(
        "The court ruled that the new policy creates immediate "
        "pressure on the local government, with conflict between "
        "competing institutional priorities."
    )
    env = v.build_v2_envelope(elins, region=None, regional_object=None)

    assert env["elins_version"] == "elins.v2.0"
    assert env["region"] is None
    assert "pipeline" in env
    assert "outputs" in env
    assert "meta" in env

    # Pipeline keys.
    expected_pipeline_keys = {
        "L1_ingest", "L2_normalize", "L3_domain", "L4_narrative",
        "L5_pressure", "L6_drift", "L7_basin", "L8_temporal",
        "L9_alignment", "L10_signature",
    }
    assert set(env["pipeline"].keys()) == expected_pipeline_keys

    # Outputs keys.
    expected_outputs_keys = {
        "collapse_state", "attractor", "state_distribution", "P0_P8",
        "geography_tier", "timeline", "multiplier",
    }
    assert set(env["outputs"].keys()) == expected_outputs_keys

    # geography_tier is None when no region passed.
    assert env["outputs"]["geography_tier"] is None

    # Timeline horizons locked.
    tl = env["outputs"]["timeline"]
    assert tl["short_term_days"] == 365
    assert tl["mid_term_days"] == 3650
    assert tl["long_term_days"] == 18250

    # Multiplier in valid range.
    m = env["outputs"]["multiplier"]
    assert 1.0 <= m <= 2.0

    # State distribution sums to ~1.
    sd = env["outputs"]["state_distribution"]
    assert abs(sum(sd.values()) - 1.0) < 1e-3

    # P0-P8 sums to ~1.
    p = env["outputs"]["P0_P8"]
    assert set(p.keys()) == {f"P{i}" for i in range(9)}
    assert abs(sum(p.values()) - 1.0) < 1e-3

    # ETF table present per primitive per horizon.
    etf_table = env["pipeline"]["L8_temporal"]["etf_table"]
    for prim in ("pressure", "tension", "trust", "drift", "contradiction", "alignment"):
        assert prim in etf_table
        for horizon in ("365", "3650", "18250"):
            assert horizon in etf_table[prim]


def test_build_v2_envelope_with_regional_sets_geography_tier(reset_stores):
    from ELINS import elins_v2_view as v
    from ELINS import standard_elins, regional_elins
    elins = standard_elins.generate_ELINS("baseline text for v2 test")
    regional = regional_elins.run_regional_elins("US", "alice")
    env = v.build_v2_envelope(
        elins, region="US", regional_object=regional,
    )
    assert env["region"] == "US"
    assert env["pipeline"]["L7_basin"]["region"] == "US"
    assert env["pipeline"]["L7_basin"]["available"] is True
    # geography_tier must be a real T-class now.
    assert env["outputs"]["geography_tier"] in {"T1", "T2", "T3", "T4"}


def test_build_v2_envelope_rejects_non_dict():
    from ELINS import elins_v2_view as v
    with pytest.raises(ValueError):
        v.build_v2_envelope("not a dict")  # type: ignore[arg-type]


# ===========================================================================
# Kernel — run_elins_v2
# ===========================================================================
def test_run_elins_v2_basic(reset_stores):
    import intelligence_kernel as ik
    out = ik.run_elins_v2("alice", "moderate pressure on the regional dispute")
    assert out["elins_version"] == "elins.v2.0"
    assert out["region"] is None
    assert out["outputs"]["geography_tier"] is None


def test_run_elins_v2_with_region(reset_stores):
    import intelligence_kernel as ik
    out = ik.run_elins_v2(
        "alice", "regional pressure test", region="US",
    )
    assert out["region"] == "US"
    assert out["outputs"]["geography_tier"] in {"T1", "T2", "T3", "T4"}


def test_run_elins_v2_empty_text_raises_value_error(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(ValueError):
        ik.run_elins_v2("alice", "")
    with pytest.raises(ValueError):
        ik.run_elins_v2("alice", "   ")
    with pytest.raises(ValueError):
        ik.run_elins_v2("alice", None)  # type: ignore[arg-type]


def test_run_elins_v2_emits_kernel_log_line(reset_stores, caplog):
    import json
    import intelligence_kernel as ik
    caplog.set_level("INFO", logger="clarityos.kernel.runs")

    ik.run_elins_v2("alice", "a structural test situation")

    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "elins_v2":
                found.append(payload)
    assert found, "expected a kernel_run line for kind=elins_v2"
    last = found[-1]
    assert last["ok"] is True
    assert last["meta"]["attractor"] in {"S1", "S2", "S3", "S4"}
    assert last["meta"]["collapse_state"] in {"none", "soft", "hard"}
    assert 1.0 <= last["meta"]["multiplier"] <= 2.0


# ===========================================================================
# Endpoint — POST /elins/v2/run
# ===========================================================================
def test_endpoint_v2_run_basic(app_module, client):
    user, sid = _make_user(app_module, "ev2_a", cohort="founder")
    r = client.post(
        "/elins/v2/run",
        headers=_auth(sid),
        json={
            "elins_version": "2.0",
            "region": None,
            "input": {
                "raw_text": "the institutional pressure is escalating sharply",
                "source_type": "operator",
                "language": "en",
            },
        },
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["elins_version"] == "elins.v2.0"
    assert body["region"] is None
    assert "outputs" in body
    assert body["outputs"]["attractor"] in {"S1", "S2", "S3", "S4"}
    assert body["outputs"]["collapse_state"] in {"none", "soft", "hard"}
    assert body["outputs"]["geography_tier"] is None
    assert 1.0 <= body["outputs"]["multiplier"] <= 2.0


def test_endpoint_v2_run_with_region(app_module, client):
    user, sid = _make_user(app_module, "ev2_b", cohort="founder")
    r = client.post(
        "/elins/v2/run",
        headers=_auth(sid),
        json={
            "region": "US",
            "input": {"raw_text": "regional structural assessment"},
        },
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["region"] == "US"
    assert body["outputs"]["geography_tier"] in {"T1", "T2", "T3", "T4"}
    assert body["pipeline"]["L7_basin"]["available"] is True


def test_endpoint_v2_run_400_on_empty_text(app_module, client):
    user, sid = _make_user(app_module, "ev2_c", cohort="founder")
    r = client.post(
        "/elins/v2/run",
        headers=_auth(sid),
        json={"input": {"raw_text": "   "}},
    )
    assert r.status_code == 400


def test_endpoint_v2_run_400_on_invalid_region(app_module, client):
    user, sid = _make_user(app_module, "ev2_d", cohort="founder")
    r = client.post(
        "/elins/v2/run",
        headers=_auth(sid),
        json={
            "region": "INVALID_REGION_XYZ",
            "input": {"raw_text": "test text"},
        },
    )
    assert r.status_code == 400


def test_endpoint_v2_run_401_when_unauth(app_module, client):
    r = client.post(
        "/elins/v2/run",
        json={"input": {"raw_text": "anything"}},
    )
    assert r.status_code == 401


def test_me_capabilities_includes_elins_v2(app_module, client):
    user, sid = _make_user(app_module, "ev2_cap", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    caps = r.json().get("capabilities") or []
    ids = {c.get("id") for c in caps if isinstance(c, dict)}
    assert "elins_v2" in ids


def test_health_version_4_7(app_module, client):
    r = client.get("/health")
    assert r.status_code == 200
    # v53 → 4.7, v54 → 4.8, v60 → 4.9, v67 → 4.10, v68 → 4.11, v69 → 4.12,
    # v70 → 4.13, v71 → 4.14, v72 → 4.15, v73 → 4.16, v74 → 4.17.
    # The test name pins the v53 era; the assertion tracks the current
    # minor head.
    assert r.json()["version"] == "4.23"


# ===========================================================================
# Architecture invariants
# ===========================================================================
def test_elins_v2_view_does_not_import_skills_export():
    """ARCHITECTURE.md invariant: no ClarityOS module may import from
    /skills_export/. Check actual import statements (not docstring
    mentions of the rule)."""
    import re
    import inspect
    from ELINS import elins_v2_view
    source = inspect.getsource(elins_v2_view)
    # Match either ``import skills_export`` or ``from skills_export``.
    bad_import = re.compile(
        r"^\s*(?:from|import)\s+skills_export\b", re.MULTILINE,
    )
    assert not bad_import.search(source), (
        "elins_v2_view must not import from skills_export"
    )


def test_run_elins_v2_does_not_call_route_request(reset_stores, monkeypatch):
    """Path C: no LLM dispatch. We patch route_request to raise if
    called — the test passes only if v2 never touches it."""
    import model_router as mr
    import intelligence_kernel as ik

    def boom(*a, **kw):
        raise AssertionError("route_request must not be called from run_elins_v2")

    monkeypatch.setattr(mr, "route_request", boom)
    out = ik.run_elins_v2("alice", "deterministic structural input")
    assert out["elins_version"] == "elins.v2.0"
