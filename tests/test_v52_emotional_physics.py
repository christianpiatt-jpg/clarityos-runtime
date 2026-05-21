"""
Tests for v52 — Emotional Physics kernel.

Covers:

model_router:
  * TASK_DEFAULTS['emotional_physics'] is anthropic:claude-3.7

intelligence_kernel:
  * _extract_json handles plain JSON / fenced JSON / prose-wrapped JSON
  * _extract_json returns (None, error) on malformed input
  * run_emotional_physics returns the four-layer shape + _meta
  * Malformed JSON → skeleton + _meta.parse_error (graceful degrade)
  * Missing keys → present-but-empty + _meta.parse_error mentions them
  * Empty text raises ValueError (mapped to 400 by the endpoint)
  * task='emotional_physics' resolves to the configured default
  * Kernel emits a kernel_run log line with kind='emotional_physics'

Endpoints:
  * POST /me/emotional_physics/analyze 200 happy path
  * POST /me/emotional_physics/analyze 200 graceful degrade on bad JSON
  * POST /me/emotional_physics/analyze 400 empty text
  * POST /me/emotional_physics/analyze 401 unauth
  * GET  /me capabilities includes 'emotional_physics'
  * GET  /health version starts with '4.'
"""
from __future__ import annotations

import json
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


def _valid_payload():
    """Canonical valid four-layer dict, used as a fake model response."""
    return {
        "field_curvature": {
            "intensity": "medium",
            "gradient_direction": "mixed",
            "stability": "unstable",
            "dominant_forces": ["time_pressure", "role_confusion"],
            "notes": "split between two roles",
        },
        "edge_pressure": {
            "signal_clarity": "mixed",
            "signal_intensity": "medium",
            "coherence": "fragmented",
            "perceived_posture": ["ambivalent"],
            "risk_of_misread": "high",
            "notes": "may read as distant",
        },
        "relational_primitives": {
            "trust": "fluctuating",
            "alignment": "partially_aligned",
            "boundary": "soft",
            "agency": "partial",
            "distance": "increasing",
            "dominant_pattern": ["boundary_uncertainty"],
            "notes": "boundary needs naming",
        },
        "external_expression": {
            "recommended_posture": ["clarify_intent", "set_boundary"],
            "message_guidance": ["state the constraint plainly"],
            "friction_reduction_moves": ["propose a single next checkpoint"],
            "risk_if_unchanged": "drift continues",
            "next_step": "send a 3-line clarification",
        },
    }


def _install_fake_handler(monkeypatch, response_text):
    """Replace the anthropic provider handler so route_request returns
    ``response_text`` verbatim. Mirrors the v50 thread-summary test
    pattern."""
    import model_router as mr
    captured = {"model_id": None, "prompt": None}

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        captured["model_id"] = model_id
        captured["prompt"] = prompt
        return {
            "ok": True, "model_id": model_id, "provider": "anthropic",
            "text": response_text, "mock": False, "ts": 0.0,
        }

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", fake_handler)
    return captured


# ===========================================================================
# model_router — task default
# ===========================================================================
def test_task_defaults_has_emotional_physics():
    import model_router as mr
    assert mr.TASK_DEFAULTS.get("emotional_physics") == "anthropic:claude-3.7"


# ===========================================================================
# intelligence_kernel._extract_json
# ===========================================================================
def test_extract_json_plain():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json('{"a": 1}')
    assert err is None
    assert parsed == {"a": 1}


def test_extract_json_fenced():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json('```json\n{"a": 1}\n```')
    assert err is None
    assert parsed == {"a": 1}


def test_extract_json_bare_fence():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json('```\n{"a": 1}\n```')
    assert err is None
    assert parsed == {"a": 1}


def test_extract_json_prose_wrapped():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json('Here is the analysis:\n{"a": 1, "b": [2]}\nDone.')
    assert err is None
    assert parsed == {"a": 1, "b": [2]}


def test_extract_json_malformed_returns_error():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json("not json at all")
    assert parsed is None
    assert isinstance(err, str) and err


def test_extract_json_empty_returns_error():
    import intelligence_kernel as ik
    parsed, err = ik._extract_json("   ")
    assert parsed is None
    assert isinstance(err, str) and err


def test_extract_json_array_top_level_rejected():
    """An array at the top level is JSON but not an object — kernel
    contract is a dict, so this counts as a parse error."""
    import intelligence_kernel as ik
    parsed, err = ik._extract_json("[1, 2, 3]")
    # Either the direct-parse path rejects with an explicit error or
    # the brace-block path can't find an object — both fine.
    assert parsed is None
    assert isinstance(err, str) and err


# ===========================================================================
# intelligence_kernel.run_emotional_physics
# ===========================================================================
def test_run_emotional_physics_happy_path(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    payload = _valid_payload()
    captured = _install_fake_handler(monkeypatch, json.dumps(payload))

    out = ik.run_emotional_physics("alice", "i feel stuck between two roles")

    # Four top-level keys present.
    assert set(out.keys()) >= {
        "field_curvature", "edge_pressure",
        "relational_primitives", "external_expression", "_meta",
    }
    # The model's response was merged in verbatim.
    assert out["field_curvature"]["intensity"] == "medium"
    assert out["relational_primitives"]["trust"] == "fluctuating"
    # _meta block.
    meta = out["_meta"]
    assert meta["model_id"] == "anthropic:claude-3.7"
    assert isinstance(meta["ts_ms"], int) and meta["ts_ms"] > 0
    assert meta["parse_error"] is None
    # Task was routed via TASK_DEFAULTS.
    assert captured["model_id"] == "anthropic:claude-3.7"


def test_run_emotional_physics_fence_tolerant(reset_stores, monkeypatch):
    """Model returns a fenced JSON block — kernel still parses it."""
    import intelligence_kernel as ik
    payload = _valid_payload()
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    _install_fake_handler(monkeypatch, fenced)

    out = ik.run_emotional_physics("alice", "situation text")
    assert out["_meta"]["parse_error"] is None
    assert out["edge_pressure"]["signal_clarity"] == "mixed"


def test_run_emotional_physics_graceful_degrade_on_garbage(
    reset_stores, monkeypatch,
):
    """Unparseable model output → skeleton + parse_error populated.
    Crucially, no exception is raised — the call returns a normal dict."""
    import intelligence_kernel as ik
    _install_fake_handler(monkeypatch, "lol this is not json")

    out = ik.run_emotional_physics("alice", "a situation")
    # All four keys still present.
    for k in (
        "field_curvature", "edge_pressure",
        "relational_primitives", "external_expression",
    ):
        assert k in out
        assert isinstance(out[k], dict)
        assert out[k] == {}   # skeleton — empty dict per layer
    assert isinstance(out["_meta"]["parse_error"], str)
    assert out["_meta"]["model_id"] == "anthropic:claude-3.7"


def test_run_emotional_physics_partial_response_flags_missing(
    reset_stores, monkeypatch,
):
    """Model returns valid JSON but with only two of the four required
    keys — kernel fills the rest with empty dicts and surfaces a
    ``parse_error`` listing the missing keys."""
    import intelligence_kernel as ik
    partial = {
        "field_curvature": {"intensity": "low", "notes": "calm"},
        "edge_pressure":   {"signal_clarity": "clear", "notes": "fine"},
    }
    _install_fake_handler(monkeypatch, json.dumps(partial))

    out = ik.run_emotional_physics("alice", "x")
    assert out["field_curvature"]["intensity"] == "low"
    assert out["edge_pressure"]["signal_clarity"] == "clear"
    assert out["relational_primitives"] == {}
    assert out["external_expression"] == {}
    pe = out["_meta"]["parse_error"]
    assert isinstance(pe, str)
    assert "relational_primitives" in pe
    assert "external_expression" in pe


def test_run_emotional_physics_empty_text_raises_value_error(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(ValueError):
        ik.run_emotional_physics("alice", "")
    with pytest.raises(ValueError):
        ik.run_emotional_physics("alice", "   \n  ")
    with pytest.raises(ValueError):
        ik.run_emotional_physics("alice", None)  # type: ignore[arg-type]


def test_run_emotional_physics_caps_long_input(reset_stores, monkeypatch):
    """Inputs longer than the cap are silently truncated; the call
    still succeeds and the captured prompt's user-text suffix is
    exactly at the cap."""
    import intelligence_kernel as ik
    payload = _valid_payload()
    captured = _install_fake_handler(monkeypatch, json.dumps(payload))

    # Use a sentinel character that does NOT appear in the prompt
    # template (the template is plain English + JSON braces).
    sentinel = "Z"
    overage = 500
    huge = sentinel * (ik.EMOTIONAL_PHYSICS_INPUT_CHAR_CAP + overage)
    out = ik.run_emotional_physics("alice", huge)

    assert out["_meta"]["parse_error"] is None
    assert captured["prompt"] is not None

    # The user text is appended after "SITUATION:\n" — split there and
    # measure the tail length directly.
    split_token = "SITUATION:\n"
    assert split_token in captured["prompt"]
    user_tail = captured["prompt"].split(split_token, 1)[1]
    assert len(user_tail) == ik.EMOTIONAL_PHYSICS_INPUT_CHAR_CAP
    # And the tail is all sentinel — confirms the truncation kept the
    # right slice (head of the input, not arbitrary middle).
    assert set(user_tail) == {sentinel}
    # And the template body itself does not contain the sentinel — so
    # we know our split isolated the user text correctly.
    assert sentinel not in ik._EMOTIONAL_PHYSICS_PROMPT


def test_run_emotional_physics_emits_kernel_log_line(
    reset_stores, monkeypatch, caplog,
):
    """One structured ``kernel_run`` line per call, kind=
    ``emotional_physics``, with model_id / input_len / raw_len."""
    import intelligence_kernel as ik
    payload = _valid_payload()
    _install_fake_handler(monkeypatch, json.dumps(payload))
    caplog.set_level("INFO", logger="clarityos.kernel.runs")

    ik.run_emotional_physics("alice", "a situation")

    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            line = rec.message.split(" ", 1)[1]
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("kind") == "emotional_physics":
                found.append(data)
    assert found, "expected a kernel_run log line with kind=emotional_physics"
    last = found[-1]
    assert last["ok"] is True
    assert last["meta"]["model_id"] == "anthropic:claude-3.7"
    assert last["meta"]["input_len"] > 0
    assert last["meta"]["raw_len"] > 0
    assert last["meta"]["parse_error"] is None


# ===========================================================================
# Endpoints
# ===========================================================================
def test_endpoint_analyze_happy_path(app_module, client, monkeypatch):
    payload = _valid_payload()
    _install_fake_handler(monkeypatch, json.dumps(payload))

    user, sid = _make_user(app_module, "ep_a", cohort="founder")
    r = client.post(
        "/me/emotional_physics/analyze",
        headers=_auth(sid),
        json={"text": "i feel pulled in two directions"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["field_curvature"]["intensity"] == "medium"
    assert body["external_expression"]["next_step"]
    assert body["_meta"]["model_id"] == "anthropic:claude-3.7"
    assert body["_meta"]["parse_error"] is None


def test_endpoint_analyze_graceful_degrade(app_module, client, monkeypatch):
    """Model returns garbage → endpoint still 200 with skeleton +
    parse_error in _meta. Never 5xx."""
    _install_fake_handler(monkeypatch, "not json")

    user, sid = _make_user(app_module, "ep_b", cohort="founder")
    r = client.post(
        "/me/emotional_physics/analyze",
        headers=_auth(sid),
        json={"text": "a complex situation"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["field_curvature"] == {}
    assert isinstance(body["_meta"]["parse_error"], str)


def test_endpoint_analyze_400_on_empty_text(app_module, client):
    user, sid = _make_user(app_module, "ep_c", cohort="founder")
    r = client.post(
        "/me/emotional_physics/analyze",
        headers=_auth(sid),
        json={"text": "   "},
    )
    assert r.status_code == 400


def test_endpoint_analyze_401_when_unauth(app_module, client):
    """No X-Session-ID header → 401 via require_session."""
    r = client.post(
        "/me/emotional_physics/analyze",
        json={"text": "anything"},
    )
    # require_session raises 401 with structured error_response body.
    assert r.status_code == 401


# ===========================================================================
# /me capabilities + /health version
# ===========================================================================
def test_me_capabilities_lists_emotional_physics(app_module, client):
    user, sid = _make_user(app_module, "cap_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    caps = r.json().get("capabilities") or []
    ids = {c.get("id") for c in caps if isinstance(c, dict)}
    assert "emotional_physics" in ids


def test_health_version_4_x(app_module, client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["version"].startswith("4.")
