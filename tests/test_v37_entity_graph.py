"""
Tests for v37 — Cross-cluster entity graph + ELINS network view.

Covers:
* elins_entity_graph: extraction, build, merge, neighbours, timeseries,
  search, and determinism.
* elins_project entity graph snapshots: save / load latest / load at /
  list snapshots.
* elins_scheduler integration: the macro pass updates the entity graph
  and is safe when no prior graph exists.
* Endpoints: /elins/entities/search, /elins/entities/{e}/neighbors,
  /elins/entities/{e}/timeseries, /founder/elins/entity_graph/raw +
  auth gates.
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Synthetic ELINS run helper — tiny fixture used to drive the graph
# builder deterministically without running the full pipeline.
# ---------------------------------------------------------------------------
def _synth_run(*, region, ts, anchors, ep_mean=0.5, domain_top="geopolitical",
               topic_hint=None):
    return {
        "region_code": region,
        "topic_hint": topic_hint,
        "regional_run_ts": ts,
        "input_phase": {"text": "", "ts": ts},
        "primitives": {"intensities": {"pressure": 0.5}},
        "domain_mapping": {
            "scores": {domain_top: 1.0, "economic": 0.2},
            "effective_top": domain_top,
            "top": domain_top, "hint": None,
        },
        "ep_field_summary": {"intensity_mean": ep_mean,
                             "stress_total": 0.0, "relief_total": 0.0,
                             "net": 0.0, "dominant": "balanced"},
        "external_signals": {
            "present": True, "region_code": region,
            "anchors": list(anchors), "signals": [], "domain_bias": {},
        },
        "synthesis": {"top_primitive": "pressure", "external_anchors": list(anchors)},
        "output_object": {"scenario_id": f"sc_{region}_{int(ts)}", "ts": ts,
                          "version": "elins.regional.v35.1"},
    }


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------
def test_extract_entities_pulls_eso_anchors(reset_stores):
    import elins_entity_graph as eg
    run = _synth_run(region="MEA", ts=1000.0,
                     anchors=["Gulf shipping disruption", "OPEC supply posture"])
    ents = eg.extract_entities(run)
    names = [e["name"] for e in ents]
    assert "Gulf shipping disruption" in names
    assert "OPEC supply posture" in names


def test_extract_entities_lexical_word_boundary(reset_stores):
    import elins_entity_graph as eg
    # "raise" must NOT trigger "AI"
    run = _synth_run(region="US", ts=1000.0, anchors=[])
    run["input_phase"]["text"] = "Pressure may raise concern but no AI here."
    ents = eg.extract_entities(run)
    names = [e["name"] for e in ents]
    # "AI" only matches when present as its own word — both "raise" and "AI"
    # in the same text means "AI" still matches via the standalone word.
    assert "AI" in names
    # Now scenario without standalone AI:
    run2 = _synth_run(region="US", ts=1000.0, anchors=[])
    run2["input_phase"]["text"] = "Pressure may raise concern; the regulator is uneven."
    ents2 = eg.extract_entities(run2)
    names2 = [e["name"] for e in ents2]
    assert "AI" not in names2


def test_extract_entities_includes_topic_hint(reset_stores):
    import elins_entity_graph as eg
    run = _synth_run(region="US", ts=1000.0, anchors=[],
                     topic_hint="Senate vote on antitrust")
    ents = eg.extract_entities(run)
    assert any(e["name"] == "Senate vote on antitrust" for e in ents)


def test_extract_entities_dedupes_case_insensitive(reset_stores):
    import elins_entity_graph as eg
    run = _synth_run(region="US", ts=1000.0,
                     anchors=["Senate", "senate"])
    ents = eg.extract_entities(run)
    names = [e["name"] for e in ents]
    # Only the first form survives ("Senate"), case-insensitive dedupe.
    assert names.count("Senate") == 1
    assert "senate" not in names


# ---------------------------------------------------------------------------
# build_entity_graph
# ---------------------------------------------------------------------------
def test_build_entity_graph_from_synthetic_runs(reset_stores):
    import elins_entity_graph as eg
    runs = [
        _synth_run(region="US", ts=1000.0, anchors=["Federal Reserve rate path", "Senate filibuster procedural vote"]),
        _synth_run(region="EU", ts=1100.0, anchors=["ECB inflation guidance", "Brussels migration package"]),
        _synth_run(region="MEA", ts=1200.0, anchors=["Iran proxy escalation", "OPEC supply posture"]),
    ]
    g = eg.build_entity_graph(runs)
    # Each run yields >= 2 entities → edges across pairs.
    assert len(g["entities"]) >= 6
    assert len(g["edges"]) >= 3
    # Each entity has degree >= 1
    for name, rec in g["entities"].items():
        assert rec["degree"] >= 1
    # updated_ts == max ts seen
    assert g["updated_ts"] == 1200.0


def test_build_entity_graph_with_no_runs(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([])
    assert g["entities"] == {}
    assert g["edges"] == {}
    assert g["version"] == eg.GRAPH_VERSION


def test_build_entity_graph_rejects_non_dict(reset_stores):
    import elins_entity_graph as eg
    with pytest.raises(ValueError):
        eg.build_entity_graph(["not a dict"])


def test_build_entity_graph_is_deterministic(reset_stores):
    import elins_entity_graph as eg
    runs = [
        _synth_run(region="US", ts=1000.0, anchors=["A", "B"]),
        _synth_run(region="EU", ts=1100.0, anchors=["B", "C"]),
    ]
    a = eg.build_entity_graph(runs)
    b = eg.build_entity_graph(runs)
    assert a == b


# ---------------------------------------------------------------------------
# merge_entity_graph
# ---------------------------------------------------------------------------
def test_merge_entity_graph_combines_edges_and_entities(reset_stores):
    import elins_entity_graph as eg
    g1 = eg.build_entity_graph([
        _synth_run(region="US", ts=1000.0, anchors=["A", "B"]),
    ])
    g2 = eg.build_entity_graph([
        _synth_run(region="EU", ts=2000.0, anchors=["B", "C"]),
    ])
    merged = eg.merge_entity_graph(g1, g2)
    assert set(merged["entities"].keys()) == {"A", "B", "C"}
    # B should be present in both clusters
    assert set(merged["entities"]["B"]["clusters"]) == {"US", "EU"}
    # B should appear in edges with A and C
    a_b = eg.get_entity_neighbors(merged, "B", limit=10)
    names = [n["name"] for n in a_b]
    assert set(names) == {"A", "C"}
    assert merged["updated_ts"] == 2000.0


def test_merge_entity_graph_with_empty_existing(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A", "B"])])
    merged = eg.merge_entity_graph(eg.EMPTY_GRAPH, g)
    assert merged["entities"] == g["entities"]
    assert merged["edges"] == g["edges"]


def test_merge_entity_graph_pure_input_unchanged(reset_stores):
    import elins_entity_graph as eg
    g1 = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A", "B"])])
    snap = {"entities": dict(g1["entities"]), "edges": dict(g1["edges"]),
            "version": g1["version"], "updated_ts": g1["updated_ts"]}
    g2 = eg.build_entity_graph([_synth_run(region="EU", ts=2000.0, anchors=["B", "C"])])
    eg.merge_entity_graph(g1, g2)
    # Top-level dicts of g1 must be unchanged.
    assert g1["entities"].keys() == snap["entities"].keys()
    assert g1["edges"].keys() == snap["edges"].keys()


def test_merge_entity_graph_is_deterministic(reset_stores):
    import elins_entity_graph as eg
    g1 = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A", "B"])])
    g2 = eg.build_entity_graph([_synth_run(region="EU", ts=2000.0, anchors=["B", "C"])])
    a = eg.merge_entity_graph(g1, g2)
    b = eg.merge_entity_graph(g1, g2)
    assert a == b


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------
def test_get_entity_neighbors_orders_by_weight(reset_stores):
    import elins_entity_graph as eg
    runs = [
        _synth_run(region="US", ts=1000.0, anchors=["A", "B"], ep_mean=0.9),
        _synth_run(region="US", ts=1100.0, anchors=["A", "B"], ep_mean=0.9),  # repeat boosts A-B
        _synth_run(region="EU", ts=1200.0, anchors=["A", "C"], ep_mean=0.1),
    ]
    g = eg.build_entity_graph(runs)
    nbrs = eg.get_entity_neighbors(g, "A")
    assert nbrs[0]["name"] == "B"
    assert nbrs[0]["weight"] > nbrs[1]["weight"]


def test_get_entity_neighbors_unknown_returns_empty(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A", "B"])])
    assert eg.get_entity_neighbors(g, "Z") == []


def test_get_entity_neighbors_validates(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([])
    with pytest.raises(ValueError):
        eg.get_entity_neighbors(g, "")


def test_get_entity_timeseries_chronological(reset_stores):
    import elins_entity_graph as eg
    runs = [
        _synth_run(region="EU", ts=2000.0, anchors=["X", "Y"], ep_mean=0.4),
        _synth_run(region="US", ts=1000.0, anchors=["X", "Z"], ep_mean=0.6),
    ]
    g = eg.build_entity_graph(runs)
    series = eg.get_entity_timeseries(g, "X")
    assert [a["ts"] for a in series] == [1000.0, 2000.0]


def test_search_entities_substring(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([
        _synth_run(region="US", ts=1000.0, anchors=["Federal Reserve rate path", "Senate filibuster"]),
        _synth_run(region="EU", ts=1100.0, anchors=["ECB inflation guidance"]),
    ])
    rows = eg.search_entities(g, "fed")
    names = [r["name"] for r in rows]
    assert "Federal Reserve rate path" in names
    # case-insensitive
    rows2 = eg.search_entities(g, "FED")
    assert [r["name"] for r in rows2] == names


def test_search_entities_empty_query_returns_all(reset_stores):
    import elins_entity_graph as eg
    g = eg.build_entity_graph([
        _synth_run(region="US", ts=1000.0, anchors=["A", "B"]),
    ])
    rows = eg.search_entities(g, "")
    assert {r["name"] for r in rows} == {"A", "B"}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_save_and_load_latest_entity_graph(reset_stores):
    import elins_entity_graph as eg
    from ELINS import elins_project
    g = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A", "B"])])
    snap_id = elins_project.save_entity_graph(g, ts=1234.5)
    assert snap_id
    loaded = elins_project.load_latest_entity_graph()
    assert loaded is not None
    assert loaded["graph"]["entities"].keys() == g["entities"].keys()


def test_load_entity_graph_at_specific_ts(reset_stores):
    import elins_entity_graph as eg
    from ELINS import elins_project
    g1 = eg.build_entity_graph([_synth_run(region="US", ts=1000.0, anchors=["A"])])
    elins_project.save_entity_graph(g1, ts=1.0)
    g2 = eg.build_entity_graph([_synth_run(region="EU", ts=2000.0, anchors=["B", "C"])])
    elins_project.save_entity_graph(g2, ts=2.0)
    rec1 = elins_project.load_entity_graph_at(1.0)
    rec2 = elins_project.load_entity_graph_at(2.0)
    assert rec1 is not None and rec2 is not None
    assert set(rec1["graph"]["entities"].keys()) == {"A"}
    assert set(rec2["graph"]["entities"].keys()) == {"B", "C"}


def test_save_entity_graph_rejects_invalid(reset_stores):
    from ELINS import elins_project
    with pytest.raises(ValueError):
        elins_project.save_entity_graph("not a dict", ts=1.0)
    with pytest.raises(ValueError):
        elins_project.save_entity_graph({"entities": {}}, ts=1.0)  # missing edges


# ---------------------------------------------------------------------------
# Macro scheduler integration
# ---------------------------------------------------------------------------
def test_macro_scheduler_creates_entity_graph(reset_stores):
    import elins_scheduler, elins_scheduler_config
    from ELINS import elins_project
    # Enable ESO so each regional run contributes anchor entities and the
    # graph picks up co-occurrence edges within each region.
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["entity_graph_id"]
    assert summary["entity_count"] > 0
    assert summary["edge_count"] > 0
    snap = elins_project.load_latest_entity_graph()
    assert snap is not None
    assert snap["graph"]["entities"]


def test_macro_scheduler_runs_without_eso(reset_stores):
    """cloud_only mode still produces a (possibly thinly-edged) graph."""
    import elins_scheduler
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["entity_graph_id"]
    # Entities may exist (regional scaffolds match a few lexical entries)
    # even without ESO; edges may be zero, which is fine.
    assert summary["entity_count"] >= 0
    assert summary["edge_count"] >= 0


def test_macro_scheduler_merges_into_existing_graph(reset_stores):
    import elins_scheduler, elins_scheduler_config
    from ELINS import elins_project
    # First pass — no ESO.
    a = elins_scheduler._run_macro_elins_once(force=True)
    # Second pass — flip ESO on so anchor entities show up.
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    b = elins_scheduler._run_macro_elins_once(force=True)
    assert b["entity_count"] >= a["entity_count"]
    snap = elins_project.load_latest_entity_graph()
    # Some MEA anchor should now exist.
    names = set((snap["graph"].get("entities") or {}).keys())
    assert any("Iran" in n or "Gulf" in n for n in names)


def test_macro_scheduler_safe_with_no_prior_graph(reset_stores):
    import elins_scheduler
    from ELINS import elins_project
    # No prior snapshot
    assert elins_project.load_latest_entity_graph() is None
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["entity_graph_id"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_endpoint_search_no_graph_yet(app_module, client):
    user, sid = _make_user(app_module, "es_a", cohort="founder")
    r = client.get("/elins/entities/search?q=fed", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["entities"] == []


def test_endpoint_search_after_macro_pass(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "es_b", cohort="founder")
    r = client.get("/elins/entities/search?q=federal", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    names = [e["name"] for e in body["entities"]]
    assert any("Federal" in n for n in names)


def test_endpoint_search_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "es_lurker", cohort=None)
    r = client.get("/elins/entities/search?q=x", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_neighbors_returns_graph(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "en_a", cohort="founder")
    # Pick an anchor name that the macro pass produces.
    name = "Federal Reserve rate path"
    r = client.get(
        f"/elins/entities/{name}/neighbors", headers=_auth(sid),
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["entity"] == name
    assert "summary" in body and "neighbors" in body
    assert isinstance(body["neighbors"], list)


def test_endpoint_neighbors_404_unknown(app_module, client):
    user, sid = _make_user(app_module, "en_b", cohort="founder")
    r = client.get(
        "/elins/entities/Definitely Not An Entity/neighbors", headers=_auth(sid),
    )
    assert r.status_code == 404


def test_endpoint_timeseries_returns_appearances(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "et_a", cohort="founder")
    r = client.get(
        "/elins/entities/Federal Reserve rate path/timeseries", headers=_auth(sid),
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["timeseries"], list)
    assert len(body["timeseries"]) >= 2  # appears in both macro passes


def test_endpoint_timeseries_404_unknown(app_module, client):
    user, sid = _make_user(app_module, "et_b", cohort="founder")
    r = client.get(
        "/elins/entities/Nope/timeseries", headers=_auth(sid),
    )
    assert r.status_code == 404


def test_endpoint_raw_graph_founder_only(app_module, client):
    user, sid = _make_user(app_module, "rg_outsider", cohort=None)
    r = client.get("/founder/elins/entity_graph/raw", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_raw_graph_returns_payload(app_module, client):
    import elins_scheduler
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "rg_a", cohort="founder")
    r = client.get("/founder/elins/entity_graph/raw", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert "graph" in body
    assert "entities" in body["graph"] and "edges" in body["graph"]
    assert body["snapshot"] is not None
    assert {"id", "ts", "entity_count", "edge_count", "version"} <= set(body["snapshot"].keys())


def test_endpoint_raw_graph_empty_when_no_pass(app_module, client):
    user, sid = _make_user(app_module, "rg_b", cohort="founder")
    r = client.get("/founder/elins/entity_graph/raw", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot"] is None
    assert body["graph"]["entities"] == {}


# ---------------------------------------------------------------------------
# UI shape lockdown
# ---------------------------------------------------------------------------
def test_ui_shape_for_search(app_module, client):
    import elins_scheduler
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ui_s", cohort="founder")
    r = client.get("/elins/entities/search", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert {"ok", "q", "entities", "count", "graph_updated_ts"} <= set(body.keys())
    if body["entities"]:
        e0 = body["entities"][0]
        assert {"name", "degree", "ep_mean", "top_domains", "clusters"} <= set(e0.keys())


def test_ui_shape_for_neighbors(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ui_n", cohort="founder")
    r = client.get(
        "/elins/entities/Federal Reserve rate path/neighbors",
        headers=_auth(sid),
    )
    body = r.json()
    assert {"ok", "entity", "summary", "neighbors"} <= set(body.keys())
    summary = body["summary"]
    assert {"degree", "clusters", "ep_mean", "domains"} <= set(summary.keys())
    if body["neighbors"]:
        n0 = body["neighbors"][0]
        assert {"name", "weight", "co_occurrences", "first_ts", "last_ts", "top_domains"} <= set(n0.keys())
