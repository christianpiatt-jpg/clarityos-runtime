"""
Tests for v41 — Perplexity real wiring + kernel hardening.

All tests run in mock mode (no real HTTP). The "live" path is exercised
via monkey-patching ``perplexity_oracle._call_perplexity`` so we never
hit the network.

Covers:
* perplexity_oracle:
  - mock-mode determinism + augmented v41 ESO shape
  - sanitize_eso strips body/html keys, drops HTML tags, truncates long strings
  - _extract_json tolerates fences + prose
  - _normalize_to_eso produces valid v41 shape
  - provider_status reflects env config
* intelligence_kernel:
  - _maybe_fetch_eso never calls oracle in cloud_only mode
  - _maybe_fetch_eso tags source on success
  - oracle failure → eso=None, run still succeeds, last_error_ts recorded
  - eso_source on regional run reflects actual fetch
  - log_kernel_run is invoked on every run_* path
* kernel_logging:
  - safe_meta strips forbidden keys + truncates long values
  - log_kernel_run returns a JSON-clean record
* /me:
  - exposes external_signal_mode + eso_source at top level
  - eso_source reflects current state (none / mock / perplexity)
* /founder/intelligence/kernel/status:
  - includes perplexity block with configured/mode/last_error_ts
"""
from __future__ import annotations

import json
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


def _make_user(app_module, username, cohort="founder", *, signal_mode=None):
    import secrets, time
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    patch = {}
    if cohort:
        patch["cohort"] = cohort
    if signal_mode is not None:
        patch["external_signal_mode"] = signal_mode
    if patch:
        users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# perplexity_oracle — mock-mode determinism + augmented shape
# ---------------------------------------------------------------------------
def test_mock_eso_has_v41_shape(reset_stores):
    import perplexity_oracle as po
    eso = po.fetch_basin_signals("US")
    # Augmented v41 fields
    for k in ("sources", "facts", "entities", "timestamps", "confidence", "source"):
        assert k in eso, f"missing {k!r}"
    # Legacy v35 fields preserved
    for k in ("region_code", "signals", "anchors", "domain_bias",
              "fetched_at", "version", "mock", "user"):
        assert k in eso, f"legacy field missing {k!r}"
    assert eso["source"] == "mock"
    assert isinstance(eso["confidence"], float)
    assert 0.0 <= eso["confidence"] <= 1.0


def test_mock_eso_is_deterministic(reset_stores):
    import perplexity_oracle as po
    a = po.fetch_basin_signals("MEA")
    b = po.fetch_basin_signals("MEA")
    assert a == b


def test_mock_eso_per_region_distinct(reset_stores):
    import perplexity_oracle as po
    a = po.fetch_basin_signals("US")
    b = po.fetch_basin_signals("MEA")
    assert a["facts"] != b["facts"]


def test_mock_mode_explicit(reset_stores):
    import perplexity_oracle as po
    eso = po.fetch_basin_signals("US", mode="mock")
    assert eso["source"] == "mock"
    assert eso["mock"] is True


def test_off_mode_returns_none(reset_stores):
    import perplexity_oracle as po
    assert po.fetch_basin_signals("US", mode="off") is None


# ---------------------------------------------------------------------------
# sanitize_eso
# ---------------------------------------------------------------------------
def test_sanitize_strips_body_and_html_keys(reset_stores):
    import perplexity_oracle as po
    dirty = {
        "facts": ["fact one"],
        "body": "full article body" * 200,
        "html_content": "<html>x</html>",
        "raw_body": "x" * 5000,
        "article_body": "y",
        "content": "this content key is dropped too",
    }
    clean = po.sanitize_eso(dirty)
    for forbidden in ("body", "html_content", "raw_body", "article_body", "content"):
        assert forbidden not in clean
    assert "facts" in clean


def test_sanitize_strips_html_tags(reset_stores):
    import perplexity_oracle as po
    dirty = {"facts": ["<b>bold fact</b>", "<a href='x'>link</a>"]}
    clean = po.sanitize_eso(dirty)
    assert "<b>" not in clean["facts"][0]
    assert "<a" not in clean["facts"][1]
    assert "bold fact" in clean["facts"][0]


def test_sanitize_truncates_long_strings(reset_stores):
    import perplexity_oracle as po
    dirty = {"facts": ["x" * 5000]}
    clean = po.sanitize_eso(dirty)
    assert len(clean["facts"][0]) <= 2000


def test_sanitize_handles_nested_dicts(reset_stores):
    import perplexity_oracle as po
    dirty = {
        "facts": ["ok"],
        "signals": [{"key": "pressure", "anchor": "<i>thing</i>", "body": "drop me"}],
    }
    clean = po.sanitize_eso(dirty)
    assert "body" not in clean["signals"][0]
    assert "<i>" not in clean["signals"][0]["anchor"]


def test_sanitize_returns_none_for_non_dict(reset_stores):
    import perplexity_oracle as po
    assert po.sanitize_eso(None) is None
    assert po.sanitize_eso("not a dict") is None
    assert po.sanitize_eso(42) is None


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------
def test_extract_json_plain(reset_stores):
    import perplexity_oracle as po
    parsed = po._extract_json('{"facts": ["a"], "confidence": 0.8}')
    assert parsed["facts"] == ["a"]


def test_extract_json_with_code_fence(reset_stores):
    import perplexity_oracle as po
    parsed = po._extract_json('```json\n{"x": 1}\n```')
    assert parsed["x"] == 1


def test_extract_json_embedded_in_prose(reset_stores):
    import perplexity_oracle as po
    parsed = po._extract_json('Sure, here it is: {"a": 1, "b": 2} hope that helps.')
    assert parsed == {"a": 1, "b": 2}


def test_extract_json_no_json_returns_none(reset_stores):
    import perplexity_oracle as po
    assert po._extract_json("just plain text") is None
    assert po._extract_json("") is None


# ---------------------------------------------------------------------------
# _normalize_to_eso (live-shape simulation)
# ---------------------------------------------------------------------------
def test_normalize_to_eso_from_simulated_response(reset_stores):
    import perplexity_oracle as po
    raw = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "facts": ["Federal Reserve held rates steady",
                              "Senate filibuster blocked vote"],
                    "entities": ["Federal Reserve", "Senate"],
                    "sources": ["https://example.com/a",
                                "https://example.com/b"],
                    "confidence": 0.82,
                }),
            },
        }],
    }
    eso = po._normalize_to_eso(raw, region_code="US")
    assert eso["region_code"] == "US"
    assert "Federal Reserve" in eso["entities"]
    assert eso["confidence"] == pytest.approx(0.82, abs=1e-3)
    # Legacy v35 fields are synthesised from the new content.
    assert isinstance(eso["signals"], list)
    assert isinstance(eso["anchors"], list)
    assert eso["anchors"][0] == "Federal Reserve held rates steady"


def test_normalize_to_eso_handles_garbage(reset_stores):
    import perplexity_oracle as po
    raw = {"choices": [{"message": {"content": "no JSON here at all"}}]}
    eso = po._normalize_to_eso(raw, region_code="US")
    assert eso["facts"] == []
    assert eso["confidence"] == 0.0


# ---------------------------------------------------------------------------
# provider_status
# ---------------------------------------------------------------------------
def test_provider_status_default_mock(reset_stores, monkeypatch):
    import perplexity_oracle as po
    monkeypatch.delenv("CLARITYOS_PERPLEXITY_API_KEY", raising=False)
    status = po.provider_status()
    assert status["configured"] is False
    assert status["mode"] == "mock"
    assert status["last_error_ts"] is None


def test_provider_status_live_when_key_set(reset_stores, monkeypatch):
    import perplexity_oracle as po
    monkeypatch.setenv("CLARITYOS_PERPLEXITY_API_KEY", "test-key-xyz")
    status = po.provider_status()
    assert status["configured"] is True
    assert status["mode"] == "live"


def test_provider_status_records_last_error(reset_stores):
    import perplexity_oracle as po
    po._record_error("simulated http 503")
    status = po.provider_status()
    assert status["last_error_ts"] is not None
    assert "simulated http 503" in status["last_error_message"]


# ---------------------------------------------------------------------------
# intelligence_kernel — _maybe_fetch_eso contract
# ---------------------------------------------------------------------------
def test_kernel_eso_skipped_in_cloud_only(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import perplexity_oracle as po
    called = {"n": 0}

    def boom(*a, **kw):
        called["n"] += 1
        return {"region_code": "US"}

    monkeypatch.setattr(po, "fetch_basin_signals", boom)
    eso = ik._maybe_fetch_eso("cloud_only", region_code="US", user="alice")
    assert eso is None
    assert called["n"] == 0


def test_kernel_eso_fetches_in_cloud_perplexity(reset_stores):
    import intelligence_kernel as ik
    eso = ik._maybe_fetch_eso(
        "cloud_perplexity", region_code="MEA", user="alice",
    )
    assert eso is not None
    assert eso["source"] in ("mock", "perplexity")


def test_kernel_eso_failure_returns_none_and_records_error(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import perplexity_oracle as po

    def boom(*a, **kw):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(po, "fetch_basin_signals", boom)
    eso = ik._maybe_fetch_eso(
        "cloud_perplexity", region_code="US", user="alice",
    )
    assert eso is None
    err = po.get_last_error()
    assert err["ts"] is not None
    assert "simulated provider failure" in err["message"]


def test_kernel_eso_unknown_region_returns_none(reset_stores):
    import intelligence_kernel as ik
    assert ik._maybe_fetch_eso("cloud_perplexity", region_code="ZZ") is None


def test_kernel_eso_sanitises_before_returning(reset_stores, monkeypatch):
    """The kernel must call sanitize_eso so HTML / body-style fields
    never reach ELINS / #G."""
    import intelligence_kernel as ik
    import perplexity_oracle as po

    def dirty_eso(*a, **kw):
        return {
            "region_code": "US",
            "signals": [], "anchors": [], "domain_bias": {},
            "facts": ["<b>fact</b>"], "entities": [],
            "sources": [], "timestamps": [], "confidence": 0.5,
            "body": "leak this if you can " * 200,
            "html_content": "<html>nope</html>",
            "mock": True,
        }

    monkeypatch.setattr(po, "fetch_basin_signals", dirty_eso)
    eso = ik._maybe_fetch_eso(
        "cloud_perplexity", region_code="US", user="alice",
    )
    assert eso is not None
    assert "body" not in eso
    assert "html_content" not in eso
    assert "<b>" not in eso["facts"][0]


def test_kernel_eso_source_tag_set(reset_stores):
    import intelligence_kernel as ik
    eso = ik._maybe_fetch_eso(
        "cloud_perplexity", region_code="US", user="alice",
    )
    assert eso["source"] == "mock"


# ---------------------------------------------------------------------------
# Run-side behaviour — failure does not break the run
# ---------------------------------------------------------------------------
def test_run_regional_ELINS_survives_oracle_failure(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import perplexity_oracle as po
    import users_store

    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    users_store.update_user("alice", {"external_signal_mode": "cloud_perplexity"})

    def boom(*a, **kw):
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(po, "fetch_basin_signals", boom)
    r = ik.run_regional_ELINS("alice", "US", topic_hint="test")
    assert r["ok"] is True
    assert r["eso_present"] is False
    assert r["eso_source"] == "none"


def test_run_regional_ELINS_eso_source_mock(reset_stores):
    import intelligence_kernel as ik
    import users_store

    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    users_store.update_user("alice", {"external_signal_mode": "cloud_perplexity"})
    r = ik.run_regional_ELINS("alice", "MEA")
    assert r["eso_present"] is True
    assert r["eso_source"] == "mock"


def test_run_regional_ELINS_eso_source_none_in_cloud_only(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_regional_ELINS("alice", "MEA")
    assert r["eso_present"] is False
    assert r["eso_source"] == "none"


# ---------------------------------------------------------------------------
# kernel_logging
# ---------------------------------------------------------------------------
def test_kernel_logging_safe_meta_strips_forbidden(reset_stores):
    import kernel_logging as kl
    meta = {
        "topic": "ok",
        "text": "DO NOT KEEP",
        "scenario_text": "ALSO NOT",
        "raw_text": "no",
        "html": "<b>x</b>",
    }
    safe = kl.safe_meta(meta)
    assert safe == {"topic": "ok"}


def test_kernel_logging_safe_meta_truncates(reset_stores):
    import kernel_logging as kl
    safe = kl.safe_meta({"long": "x" * 1000})
    assert len(safe["long"]) <= 200


def test_kernel_logging_log_kernel_run_returns_record(reset_stores):
    import kernel_logging as kl
    rec = kl.log_kernel_run(
        kind="run_c", user_id="alice", external_signal_mode="cloud_only",
        eso_source="none", duration_ms=12.3, ok=True,
        meta={"mode": "comment"},
    )
    assert rec["kind"] == "run_c"
    assert rec["ok"] is True
    assert rec["eso_source"] == "none"
    assert rec["meta"] == {"mode": "comment"}
    # Record must JSON-serialise.
    json.dumps(rec)


def test_kernel_logging_emitted_on_run_paths(reset_stores, caplog):
    import intelligence_kernel as ik
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    ik.run_c("alice", "the agency is drifting from its mandate")
    ik.run_ELINS(
        "alice", "trust between partners is eroding",
        kind="preview", persist=False,
    )
    ik.run_regional_ELINS("alice", "MEA")
    kinds = [
        json.loads(rec.message.split(" ", 1)[1])["kind"]
        for rec in caplog.records if rec.message.startswith("kernel_run ")
    ]
    assert "run_c" in kinds
    assert "run_ELINS" in kinds
    assert "run_regional_ELINS" in kinds


# ---------------------------------------------------------------------------
# /me — top-level external_signal_mode + eso_source
# ---------------------------------------------------------------------------
def test_me_exposes_top_level_signal_mode(app_module, client):
    user, sid = _make_user(app_module, "me_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["external_signal_mode"] in ("cloud_only", "cloud_perplexity")
    assert body["eso_source"] in ("none", "mock", "perplexity")


def test_me_eso_source_none_when_cloud_only(app_module, client):
    user, sid = _make_user(app_module, "me_b", cohort="founder")
    # Default is cloud_only.
    r = client.get("/me", headers=_auth(sid))
    assert r.json()["eso_source"] == "none"


def test_me_eso_source_mock_when_cloud_perplexity_no_key(app_module, client, monkeypatch):
    monkeypatch.delenv("CLARITYOS_PERPLEXITY_API_KEY", raising=False)
    user, sid = _make_user(app_module, "me_c", cohort="founder")
    client.post(
        "/me/operator_state", headers=_auth(sid),
        json={"external_signal_mode": "cloud_perplexity"},
    )
    r = client.get("/me", headers=_auth(sid))
    assert r.json()["eso_source"] == "mock"
    assert r.json()["external_signal_mode"] == "cloud_perplexity"


def test_me_eso_source_perplexity_when_key_set(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_PERPLEXITY_API_KEY", "test-key-xyz")
    user, sid = _make_user(app_module, "me_d", cohort="founder")
    client.post(
        "/me/operator_state", headers=_auth(sid),
        json={"external_signal_mode": "cloud_perplexity"},
    )
    r = client.get("/me", headers=_auth(sid))
    assert r.json()["eso_source"] == "perplexity"


# ---------------------------------------------------------------------------
# /founder/intelligence/kernel/status — perplexity block
# ---------------------------------------------------------------------------
def test_kernel_status_includes_perplexity_block(app_module, client):
    user, sid = _make_user(app_module, "ks_a", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    assert r.status_code == 200
    kernel = r.json()["kernel"]
    assert "perplexity" in kernel
    p = kernel["perplexity"]
    assert "configured" in p
    assert "mode" in p
    assert "last_error_ts" in p


def test_kernel_status_perplexity_live_when_key_set(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_PERPLEXITY_API_KEY", "test-key-xyz")
    user, sid = _make_user(app_module, "ks_b", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    p = r.json()["kernel"]["perplexity"]
    assert p["configured"] is True
    assert p["mode"] == "live"


def test_kernel_status_perplexity_mock_when_key_unset(app_module, client, monkeypatch):
    monkeypatch.delenv("CLARITYOS_PERPLEXITY_API_KEY", raising=False)
    user, sid = _make_user(app_module, "ks_c", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    p = r.json()["kernel"]["perplexity"]
    assert p["configured"] is False
    assert p["mode"] == "mock"


def test_kernel_status_perplexity_last_error_after_failure(app_module, client, monkeypatch):
    import perplexity_oracle as po
    po._record_error("simulated 503")
    user, sid = _make_user(app_module, "ks_d", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    p = r.json()["kernel"]["perplexity"]
    assert p["last_error_ts"] is not None


# ---------------------------------------------------------------------------
# Integration — endpoint contracts unchanged with v41 wiring
# ---------------------------------------------------------------------------
def test_endpoint_regional_run_returns_eso_source_field(app_module, client):
    user, sid = _make_user(
        app_module, "ee_a", cohort="founder",
        signal_mode="cloud_perplexity",
    )
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "MEA"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    # Existing eso_present field still present.
    assert body["eso_present"] is True
