"""
#196 · #199 · #200 -- one word, one refusal, one reading.

WHAT THESE PIN.

#196  ONE stop vocabulary, backend-side. Every vendor names the end of a
      generation differently and each surface used to apply the same wrong
      rule -- "anything but end_turn is a cut" -- so a normal OpenAI ``stop``
      and a normal Gemini ``STOP`` rendered "stopped early" on a finished
      reply. ``stop_vocabulary.classify_stop`` answers exactly three words,
      and a fourth KIND for absence: normal / cut / unknown / None. UNKNOWN
      is not a cut and not a completion -- it renders nothing and is logged
      ONCE per distinct token. The physics ``_meta`` carries the class beside
      the RAW token, which is what a surface names (R5.3).

#199  ONE refusal. All three gates -- ``app._require_founder``,
      ``runtime_http.require_founder`` and ``app._require_admin`` (the third
      shape: it used to answer {"error": "forbidden", "message": "Admin
      only"}) -- refuse with the SAME status and the SAME body. The
      predicates stay different; only the refusal is one.

#200  ``of_n`` is PER BEARING, as built: it counts the turns that carried
      THAT bearing, not the turns in the window. "trust: low (2 of 3)" while
      a sibling reads "(1 of 1)" is correct, and this pins it so the reading
      cannot drift back to a window count.
"""
from __future__ import annotations

import json
import logging
import secrets
import time

import pytest

from conftest import TestClient

import runtime_http as rh
import sessions_store
import stop_vocabulary as sv
import turn_record
import users_store


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _session_for(username: str, **doc) -> dict:
    import bcrypt
    if not users_store.get_user(username):
        users_store.create_user(
            username=username,
            password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
            salt="", tier="free", created_at=time.time(),
        )
    if doc:
        users_store.update_user(username, doc)
    sid = "sess_" + secrets.token_urlsafe(12)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# #196 -- the vocabulary table
# ===========================================================================

# One case per vendor word the order named, with the vendor that emits it.
NORMAL_TOKENS = [
    ("end_turn", "anthropic"),
    ("stop", "openai / ollama"),
    ("STOP", "gemini"),
    ("stop_sequence", "anthropic"),
    ("eos", "local runtimes"),
]
CUT_TOKENS = [
    ("max_tokens", "anthropic"),
    ("length", "openai"),
    ("MAX_TOKENS", "gemini"),
    ("content_filter", "openai"),
    ("SAFETY", "gemini"),
]
UNKNOWN_TOKENS = ["tool_use", "recitation", "OTHER", "function_call", "banana"]


@pytest.mark.parametrize("token,vendor", NORMAL_TOKENS)
def test_a_finished_reply_is_normal(token, vendor):
    assert sv.classify_stop(token) == sv.NORMAL, vendor
    assert sv.is_cut(token) is False


@pytest.mark.parametrize("token,vendor", CUT_TOKENS)
def test_a_truncated_reply_is_cut(token, vendor):
    assert sv.classify_stop(token) == sv.CUT, vendor
    assert sv.is_cut(token) is True


@pytest.mark.parametrize("token", UNKNOWN_TOKENS)
def test_a_word_the_table_does_not_know_is_unknown(token):
    """UNKNOWN is a THIRD kind. It must never read as a cut -- that is the
    #196 bug in the other direction."""
    assert sv.classify_stop(token) == sv.UNKNOWN
    assert sv.is_cut(token) is False


def test_absence_is_a_different_kind_from_unknown():
    """D5 -- no signal at all is not "a word I do not know". A mock reply and
    a provider that sends nothing answer None, and nothing is logged."""
    for absent in (None, "", "   ", 0, 17, [], {}):
        assert sv.classify_stop(absent) is None, absent


def test_the_same_word_from_three_vendors_folds_to_one_word():
    """What makes it ONE vocabulary rather than six: the same word in a
    different case is the same word."""
    assert sv.classify_stop("stop") == sv.classify_stop("STOP") == sv.classify_stop("Stop") == sv.NORMAL
    assert sv.classify_stop("max_tokens") == sv.classify_stop("MAX_TOKENS") == sv.CUT
    assert sv.classify_stop("  end_turn  ") == sv.NORMAL


def test_an_unknown_token_is_logged_once_and_names_the_raw_word(caplog):
    sv._reset_seen_for_tests()
    with caplog.at_level(logging.WARNING, logger="clarityos.stop_vocabulary"):
        for _ in range(5):
            assert sv.classify_stop("zzz_novel_token") == sv.UNKNOWN
        assert sv.classify_stop("other_novel_token") == sv.UNKNOWN
    lines = [r for r in caplog.records if "stop_vocabulary unknown" in r.getMessage()]
    assert len(lines) == 2, [r.getMessage() for r in lines]
    assert "zzz_novel_token" in lines[0].getMessage()
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="clarityos.stop_vocabulary"):
        sv.classify_stop("end_turn")
        sv.classify_stop("max_tokens")
    assert [r for r in caplog.records if "stop_vocabulary unknown" in r.getMessage()] == []


def test_every_table_value_is_one_of_the_two_decided_words():
    assert set(sv.STOP_VOCABULARY.values()) == {sv.NORMAL, sv.CUT}
    for key in sv.STOP_VOCABULARY:
        assert key == sv.fold(key), "table keys are the folded form"


def _install_fake_handler(monkeypatch, response_text: str, stop_reason):
    """Replace the anthropic provider handler so the kernel gets a reply
    carrying the stop signal we choose. No network."""
    import model_router as mr

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        out = {"ok": True, "model_id": model_id, "provider": "anthropic",
               "text": response_text, "mock": False, "ts": 0.0}
        if stop_reason is not _ABSENT:
            out["stop_reason"] = stop_reason
        return out

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", fake_handler)


_ABSENT = object()
_PAYLOAD = json.dumps({
    "field_curvature": {"intensity": "medium"},
    "edge_pressure": {},
    "relational_primitives": {"trust": "fluctuating"},
    "external_expression": {},
})


@pytest.mark.parametrize("raw,expected", [
    ("end_turn", "normal"),
    ("stop", "normal"),
    ("STOP", "normal"),
    ("max_tokens", "cut"),
    ("MAX_TOKENS", "cut"),
    ("SAFETY", "cut"),
    ("refusal", "unknown"),
    ("tool_use", "unknown"),
])
def test_the_physics_meta_carries_the_class_beside_the_raw_token(
    reset_stores, monkeypatch, raw, expected,
):
    """R5.3 -- the RAW vendor token stays and the class rides beside it.
    Run through the real kernel path, not a source grep: this fails if the
    wiring is removed OR if the table stops agreeing with the surface."""
    import intelligence_kernel as ik

    _install_fake_handler(monkeypatch, _PAYLOAD, raw)
    out = ik.run_emotional_physics("alice", "i feel stuck between two roles")
    meta = out["_meta"]
    assert meta["stop_reason"] == raw, "the raw token is never replaced"
    assert meta["stop_class"] == expected


def test_a_mock_reply_carries_no_class_at_all(reset_stores, monkeypatch):
    """D5 -- absence is its own kind. A provider that sends no stop signal
    puts None on the wire, not "unknown", and no surface marks."""
    import intelligence_kernel as ik

    _install_fake_handler(monkeypatch, _PAYLOAD, _ABSENT)
    out = ik.run_emotional_physics("alice", "text")
    assert out["_meta"]["stop_reason"] is None
    assert out["_meta"]["stop_class"] is None


# ===========================================================================
# #199 -- one refusal at all THREE gates
# ===========================================================================

def test_the_third_gate_now_raises_the_one_refusal(app_module):
    """``app._require_admin`` used to raise
    {"error": "forbidden", "message": "Admin only"}. It now raises the dict
    the two controller gates raise. The PREDICATE is untouched: it still
    compares the bootstrap admin username, not the controller flag."""
    import inspect

    src = inspect.getsource(app_module._require_admin)
    assert "ADMIN_ONLY_REFUSAL" in src
    assert 'error_response("forbidden"' not in src
    assert "ADMIN_USER" in src, "the predicate must not have moved"


def test_the_one_refusal_is_error_response_shaped_and_names_no_cohort(app_module):
    assert rh.ADMIN_ONLY_REFUSAL == app_module.error_response(
        "admin_only", "Admin only: this console is the controller's")
    assert set(rh.ADMIN_ONLY_REFUSAL) == {"ok", "error", "message"}
    msg = rh.ADMIN_ONLY_REFUSAL["message"]
    assert "@" not in msg and "cohort" not in msg.lower() and "founder" not in msg.lower()


def test_all_three_gates_answer_the_same_status_and_the_same_body(client):
    """The acceptance line: a member-shaped request to a route behind each of
    the three gates comes back byte-identical."""
    h = _session_for("gates199@example.com", controller=False)

    a = client.get("/founder/members", headers=h)               # app._require_founder
    b = client.get("/org/timeline/24h", headers=h)              # runtime_http.require_founder
    c = client.post("/invite/create", headers=h,                # app._require_admin
                    json={"cohort": "terrace_1"})

    assert a.status_code == b.status_code == c.status_code == 403
    assert a.json() == b.json() == c.json() == rh.ADMIN_ONLY_REFUSAL
    for r in (a, b, c):
        assert "forbidden" not in r.text
        assert "Founder cohort required" not in r.text


def test_all_three_gates_answer_the_same_body_with_NO_session(client):
    """#199's acceptance line is a request with NO session -- which never
    reaches a 403 at all. It used to fail: runtime_http's session layer
    raised a BARE STRING, so app.py's envelope handler wrapped it as
    {"error": "http_error"} while the two app gates answered
    {"error": "missing_session"}. Three gates, two bodies, one status."""
    a = client.get("/founder/members")
    b = client.get("/org/timeline/24h")
    c = client.post("/invite/create", json={"cohort": "terrace_1"})
    assert a.status_code == b.status_code == c.status_code == 401
    assert a.json() == b.json() == c.json() == rh.SESSION_MISSING_REFUSAL
    for r in (a, b, c):
        assert "http_error" not in r.text


def test_all_three_gates_answer_the_same_body_for_an_UNKNOWN_session(client):
    h = {"X-Session-ID": "sess_no_such_session_at_all"}
    a = client.get("/founder/members", headers=h)
    b = client.get("/org/timeline/24h", headers=h)
    c = client.post("/invite/create", headers=h, json={"cohort": "terrace_1"})
    assert a.status_code == b.status_code == c.status_code == 401
    assert a.json() == b.json() == c.json() == rh.SESSION_INVALID_REFUSAL


def test_every_session_layer_refusal_is_error_response_shaped(app_module):
    """runtime_http is the LOWER module and cannot import app, so its
    literals are pinned to app.error_response's shape here."""
    pairs = [
        (rh.SESSION_MISSING_REFUSAL, ("missing_session", "X-Session-ID header required")),
        (rh.SESSION_INVALID_REFUSAL, ("invalid_session", "Unknown session id")),
        (rh.SESSION_EXPIRED_REFUSAL, ("expired_session", "Session expired; log in again")),
        (rh.OPERATOR_UNRESOLVED_REFUSAL, ("operator_unresolved", "operator identity unresolved")),
    ]
    for got, (err, msg) in pairs:
        assert got == app_module.error_response(err, msg)
        assert set(got) == {"ok", "error", "message"}


# ===========================================================================
# #200 -- of_n is per bearing
# ===========================================================================

def _row(turn_index: int, bearings: dict) -> dict:
    return {"turn_index": turn_index, "bearings": dict(bearings)}


def test_of_n_counts_the_turns_that_carried_that_bearing_not_the_window():
    """#200 (CT-1 2026-09-09) -- of_n stays PER BEARING, as built. Three
    turns; trust appears in all three, boundary in only one. trust reads
    "(2 of 3)" and boundary "(1 of 1)" -- boundary must NOT read "of 3"."""
    rows = [
        _row(0, {"trust": "low", "boundary": "contested"}),
        _row(1, {"trust": "low"}),
        _row(2, {"trust": "high"}),
    ]
    head = turn_record.bearings_header(rows, last=3)
    assert head is not None
    assert head["trust"] == {"value": "low", "count": 2, "of_n": 3}
    assert head["boundary"] == {"value": "contested", "count": 1, "of_n": 1}
    assert head["trust"]["of_n"] != head["boundary"]["of_n"], "the per-bearing rule"


def test_a_tie_reads_split_and_of_n_still_counts_that_bearing():
    rows = [
        _row(0, {"trust": "low"}),
        _row(1, {"trust": "high"}),
        _row(2, {"alignment": "aligned"}),
    ]
    head = turn_record.bearings_header(rows, last=3)
    assert head["trust"]["value"] == "split"
    assert head["trust"]["of_n"] == 2          # two turns carried trust
    assert head["alignment"]["of_n"] == 1      # one carried alignment
