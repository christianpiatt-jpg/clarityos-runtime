"""
#284 -- three persist lines. Each reproduced live 09-14 by CT-1; each is one
decision, and each has a write-side pin here so it cannot ship the other way
again.

1. /el_ins/analyze stored NOTHING without a thread_id while the dashboard
   copy promised "stored under the authed operator, keyed by thread_id when
   provided" -- RECENT read "No EL/INS records yet" straight after a run.
   Now: always stored under the operator; thread_id is a TAG (blank is
   absent; never defaulted to a current thread -- #167e filed a newsletter
   reading into a relationship record that way).
2. POST /me/threads/{id}/message said "[mock openai:gpt-5.4] ..." only inside
   the reply TEXT while /session rendered the same fact as a field (#147).
   Now: ``mock`` and ``fallback_error`` are declared beside grounding_status,
   read off the last vendor call, and the error string is scrubbed of
   anything key-shaped before it rides a member wire. Never persisted on
   the message.
3. The library title wrote the argmax of a four-way tie ("[elins_v2_view]
   S1 / soft") while the surface refused to name a state ("indeterminate --
   no attractor leads. S1/S2/S3/S4 are within 5 points."). Now: the write
   path takes the same refusal, by the same rule, and the rule's constant
   and operator are READ from web/src/lib/attractor.ts so the two cannot
   drift apart silently. Existing rows stay as written (no retrofit).
"""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path

import pytest
from fastapi import FastAPI

from conftest import TestClient, seed_controller

import el_ins
import runtime_http as rh_mod
import sessions_store


_ROOT = Path(__file__).resolve().parents[1]


# ===========================================================================
# 1. /el_ins/analyze -- stored under the operator; thread_id is a tag
# ===========================================================================
@pytest.fixture
def elins_client():
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    el_ins._reset_for_tests()
    yield TestClient(app)
    el_ins._reset_for_tests()


def _op(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-284-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _analyze(client, headers, **extra):
    body = {"text": "catastrophic disaster doom", "provider_mode": "deterministic"}
    body.update(extra)
    return client.post("/el_ins/analyze", json=body, headers=headers)


def test_1_no_thread_id_is_stored_and_recent_lists_it(elins_client):
    h = _op()
    r = _analyze(elins_client, h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["thread_id"] is None
    rows = elins_client.get("/el_ins/recent", headers=h).json()["records"]
    assert len(rows) == 1                      # the run CT-1 saw vanish
    assert rows[0]["thread_id"] is None
    assert rows[0]["source"] == "on_demand"
    assert rows[0]["result"]["analysis"]["ratio_classification"] == "high_el"


def test_1_blank_thread_id_is_absent_and_never_defaulted(elins_client):
    h = _op()
    for blank in ("", " ", "\t \n"):
        r = _analyze(elins_client, h, thread_id=blank)
        assert r.status_code == 200, repr(blank)
        assert r.json()["stored"] is True
        assert r.json()["thread_id"] is None, repr(blank)
    rows = elins_client.get("/el_ins/recent", headers=h).json()["records"]
    assert len(rows) == 3
    # ABSENT, not a default: no record acquired a thread it was not given.
    assert all(row["thread_id"] is None for row in rows)


def test_1_thread_id_tags_the_record_and_only_that_record(elins_client):
    h = _op()
    assert _analyze(elins_client, h).status_code == 200                    # untagged
    r = _analyze(elins_client, h, thread_id="  lease-7  ")               # tagged (trimmed)
    assert r.json()["thread_id"] == "lease-7"
    recent = elins_client.get("/el_ins/recent", headers=h).json()["records"]
    assert [row["thread_id"] for row in recent] == ["lease-7", None]      # newest first
    by_thread = elins_client.get("/el_ins/thread/lease-7", headers=h).json()["records"]
    assert len(by_thread) == 1 and by_thread[0]["thread_id"] == "lease-7"


def test_1_an_untagged_record_is_still_the_operators_own(elins_client):
    ha, hb = _op("op_alice"), _op("op_bob")
    assert _analyze(elins_client, ha).status_code == 200
    assert elins_client.get("/el_ins/recent", headers=ha).json()["records"]
    assert elins_client.get("/el_ins/recent", headers=hb).json()["records"] == []


# ===========================================================================
# 2. /me/threads/{id}/message -- mock + fallback_error declared, scrubbed
# ===========================================================================
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _member(username: str = "writer@example.com"):
    """The recipe tests/test_store_is_written.py uses: an active membership
    (the route sits behind require_active_entitlement), the controller flag
    (unlimited on the meter), a minted op_ id, a session, an Idempotency-Key."""
    import bcrypt
    import users_store
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.set_membership(username, tier="founding_500", price=50.0, status="active")
    seed_controller(username)
    users_store.update_user(username, {"operator_id": "op_" + secrets.token_urlsafe(12)})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid, "Idempotency-Key": secrets.token_hex(8)}


def _post(client, headers, tid, text="which clause governs the deposit?"):
    h = dict(headers); h["Idempotency-Key"] = secrets.token_hex(8)
    return client.post(f"/me/threads/{tid}/message", json={"content": text}, headers=h)


def _real_answer(text="The deposit clause is clause 7."):
    """A route_request stand-in shaped like a REAL provider reply."""
    def _route(model_id, prompt, **kwargs):
        return {"ok": True, "model_id": model_id, "provider": "openai",
                "text": text, "mock": False, "ts": time.time(),
                "stop_reason": "stop", "usage": None}
    return _route


def _mock_answer(error=None):
    """model_router's own mock -- with ``error`` it is the degraded path a
    failed real call takes (fallback_error stamped)."""
    import model_router
    def _route(model_id, prompt, **kwargs):
        return model_router._mock_result(model_id, "gemini", prompt, time.time(), error=error)
    return _route


_KEYED_URL_ERROR = (
    "HTTP Error 400: Bad Request for https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyFAKE0000000000000000000000000000"
)


def test_2_the_two_fields_are_declared_on_the_wire(client, monkeypatch):
    import model_router
    import threads_vault as tv
    monkeypatch.setattr(model_router, "route_request", _mock_answer())
    user, h = _member()
    tid = tv.create_thread(user, "lease")["thread_id"]
    r = _post(client, h, tid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "mock" in body and "fallback_error" in body        # declared, beside grounding_status
    assert "grounding_status" in body
    assert body["mock"] is True                              # a mock answered
    assert body["fallback_error"] is None                    # ... and nothing failed: absent, not ""
    assert body["assistant_message"]["content"].startswith("[mock ")   # the text is unchanged (additive)


def test_2_a_real_provider_answer_declares_mock_false(client, monkeypatch):
    import model_router
    import threads_vault as tv
    monkeypatch.setattr(model_router, "route_request", _real_answer())
    user, h = _member()
    tid = tv.create_thread(user, "lease")["thread_id"]
    body = _post(client, h, tid).json()
    assert body["mock"] is False
    assert body["fallback_error"] is None
    assert "[mock" not in body["assistant_message"]["content"]


def test_2_a_mock_standing_in_for_a_failed_call_declares_both_and_scrubs(client, monkeypatch):
    import model_router
    import threads_vault as tv
    monkeypatch.setattr(model_router, "route_request", _mock_answer(error=_KEYED_URL_ERROR))
    user, h = _member()
    tid = tv.create_thread(user, "lease")["thread_id"]
    r = _post(client, h, tid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mock"] is True
    fe = body["fallback_error"]
    assert isinstance(fe, str) and fe
    assert "HTTP Error 400" in fe                            # the fact rides
    assert "AIza" not in fe and "key=" not in fe            # the credential does not
    assert "[url]" in fe and "generativelanguage" not in fe # nor the vendor URL
    assert "AIza" not in r.text                              # ... anywhere on the wire
    # never persisted on the message: the stored turn carries neither key.
    _meta, msgs = tv.get_thread(user, tid)
    assert msgs and all("mock" not in m and "fallback_error" not in m for m in msgs)


def test_2_the_kernel_log_line_carries_mock_and_never_the_error_text(reset_stores, monkeypatch, caplog):
    import intelligence_kernel as ik
    import model_router
    import threads_vault as tv
    monkeypatch.setattr(model_router, "route_request", _mock_answer(error=_KEYED_URL_ERROR))
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    tid = tv.create_thread("alice", "chat")["thread_id"]
    out = ik.run_thread_message("alice", tid, "how tall?")
    assert out["mock"] is True and out["fallback_error"] == _KEYED_URL_ERROR[:200]
    recs = [json.loads(r.message.split(" ", 1)[1]) for r in caplog.records
            if r.message.startswith("kernel_run ")]
    recs = [p for p in recs if p.get("kind") == "run_thread_message"]
    assert recs, "expected a run_thread_message kernel_run line"
    meta = recs[-1]["meta"]
    assert meta["mock"] is True
    assert "fallback_error" not in meta
    assert "AIza" not in caplog.text and "generativelanguage" not in caplog.text


def _sequence(*responses):
    """A route_request stand-in that answers each call from a fixed list."""
    queue = list(responses)
    def _route(model_id, prompt, **kwargs):
        r = dict(queue.pop(0)) if queue else {"ok": True, "text": "(exhausted)", "mock": True}
        r.setdefault("model_id", model_id)
        return r
    return _route


def test_2_the_flags_follow_the_text_that_became_the_reply(reset_stores, monkeypatch):
    """A #cite turn whose reply is ungrounded fires ONE retry. If the retry
    comes back empty, the FIRST call's text stands as the reply -- and so
    must its flags: the last call was real and clean, the answer was a
    mock that stood in for a failure. When the retry's text stands, the
    flags are the retry's."""
    import intelligence_kernel as ik
    import model_router
    import threads_vault as tv
    first = dict(model_router._mock_result("m", "gemini", "p", 0.0, error="E1"),
                 text="The value is 42.")                     # ungrounded -> a retry fires
    empty_real = {"ok": True, "provider": "openai", "text": "", "mock": False,
                  "ts": 0.0, "stop_reason": "stop", "usage": None}
    monkeypatch.setattr(model_router, "route_request", _sequence(first, empty_real))
    tid = tv.create_thread("alice", "chat")["thread_id"]
    out = ik.run_thread_message("alice", tid, "#cite what is it?")
    assert len(out["vendor_calls"]) == 2                          # the retry was made
    assert out["assistant_message"]["content"] == "The value is 42."   # ... and the first text stood
    assert out["mock"] is True and out["fallback_error"] == "E1"  # so the first call's flags

    real_retry = dict(empty_real, text="The value is 42 [source: the lease, clause 7].")
    monkeypatch.setattr(model_router, "route_request", _sequence(first, real_retry))
    tid2 = tv.create_thread("alice", "chat2")["thread_id"]
    out2 = ik.run_thread_message("alice", tid2, "#cite what is it?")
    assert len(out2["vendor_calls"]) == 2
    assert out2["assistant_message"]["content"].startswith("The value is 42 [")
    assert out2["mock"] is False and out2["fallback_error"] is None  # the retry answered


@pytest.mark.parametrize("raw, expect", [
    (None, None),
    ("", None),                                                      # absent stays absent
    ("HTTP Error 401: Unauthorized", "HTTP Error 401: Unauthorized"),
    ("<urlopen error [Errno 11001] getaddrinfo failed>", "<urlopen error [Errno 11001] getaddrinfo failed>"),
    ("bad url https://h/p?key=AIzaSyFAKE00000000000000000000000000&x=1", "bad url [url]"),
    ("connect to http://127.0.0.1:11434/api/generate refused", "connect to [url] refused"),  # an internal host
    ("api_key=sk-proj-abcdefghijklmnop rejected", "api_key=[redacted] rejected"),
    ("token=abc123456789 expired", "token=[redacted] expired"),
    ("Authorization: Bearer sk-ant-api03-abcdefghijkl", "Authorization: bearer [redacted]"),
    ("Authorization: Bearer abc", "Authorization: bearer [redacted]"),        # any length after the word
    ("leaked sk-ant-api03-abcdefghijkl in body", "leaked [redacted] in body"),
    ("apikeyAIzaSyFAKE00000000000000000000000000 rejected", "apikey[redacted] rejected"),  # no boundary needed
    ("xai-abcdefghijkl and gsk_abcdefghijkl", "[redacted] and [redacted]"),
    ("monkey=1 is not a key", "monkey=1 is not a key"),               # word boundary holds
    ("risk-based-approach failed", "risk-based-approach failed"),    # a bare sk- still needs its boundary
])
def test_2_scrub_credentials(raw, expect):
    import runtime_privacy
    assert runtime_privacy.scrub_credentials(raw) == expect


# ===========================================================================
# 3. the write path takes the render path's refusal
# ===========================================================================
_LEVEL = {"S1": 0.25, "S2": 0.25, "S3": 0.25, "S4": 0.25}     # CT-1's read: within 5 points
_NEAR = {"S1": 0.27, "S2": 0.25, "S3": 0.24, "S4": 0.24}      # a near-tie inside the epsilon
_LEAD = {"S1": 0.21, "S2": 0.21, "S3": 0.36, "S4": 0.21}      # the real discriminating read (15 pts)


def test_3_the_rule_refuses_a_level_field_and_names_a_leader():
    from ELINS import elins_v2_view as v
    tie = v.attractor_verdict(_LEVEL, "S1")
    assert tie["determinate"] is False and tie["state"] is None
    assert tie["leaders"] == ["S1", "S2", "S3", "S4"]           # state order on a tie
    near = v.attractor_verdict(_NEAR, "S1")
    assert near["determinate"] is False and near["leaders"] == ["S1", "S2", "S3", "S4"]
    lead = v.attractor_verdict(_LEAD, "S1")
    assert lead["determinate"] is True and lead["state"] == "S3"
    assert abs(lead["gap"] - 0.15) < 1e-9 and lead["leaders"] == []


def test_3_an_unusable_distribution_keeps_the_given_attractor():
    from ELINS import elins_v2_view as v
    for dist in (None, {}, "S1", {"S1": 0.9}, {"S1": "x", "S2": "y"}):
        out = v.attractor_verdict(dist, "S2")
        assert out == {"determinate": True, "state": "S2", "gap": 1.0, "leaders": []}, dist
    # a null weight counts as 0, as JS Number(null) does on the render path
    out = v.attractor_verdict({"S1": None, "S2": 0.5, "S3": 0.3, "S4": 0.2}, "S1")
    assert out["determinate"] is True and out["state"] == "S2"


def test_3_epsilon_operator_and_word_are_read_from_the_web_rule():
    """The server rule mirrors web/src/lib/attractor.ts. The constant, the
    strict-less-than and the label are READ from that file, not retyped,
    so a change on either side fails here first."""
    from ELINS import elins_v2_view as v
    ts = (_ROOT / "web" / "src" / "lib" / "attractor.ts").read_bytes().decode("utf-8")
    m = re.search(r"export const ATTRACTOR_TIE_EPSILON\s*=\s*([0-9.]+)\s*;", ts)
    assert m, "web/src/lib/attractor.ts no longer exports ATTRACTOR_TIE_EPSILON"
    assert float(m.group(1)) == v.ATTRACTOR_TIE_EPSILON == 0.05
    assert re.search(r"gap\s*<\s*ATTRACTOR_TIE_EPSILON", ts)                     # strict <, the same doubles on both sides
    assert re.search(r"pairs\[0\]\.w\s*-\s*p\.w\s*<\s*ATTRACTOR_TIE_EPSILON", ts)  # leaders: same strictness
    m = re.search(r'export const INDETERMINATE_LABEL\s*=\s*"([^"]+)"', ts)
    assert m and m.group(1).startswith(v.INDETERMINATE_ATTRACTOR)   # "indeterminate — no attractor leads"


def test_3_a_level_field_title_says_indeterminate_and_the_envelope_is_untouched(reset_stores):
    from ELINS import ingestion_bus as ib
    import library_store
    env = {"outputs": {"attractor": "S1", "collapse_state": "soft", "state_distribution": dict(_LEVEL)}}
    item_id = ib.persist_to_library("alice", source="elins_v2_view", region=None,
                                    raw_text="pasted from the tab", envelope=env)
    row = library_store.get(item_id)
    assert row["title"] == "[elins_v2_view] indeterminate / soft"      # was "[elins_v2_view] S1 / soft"
    # the wire envelope is stored verbatim: outputs.attractor is still the argmax
    assert row["metadata"]["envelope"]["outputs"]["attractor"] == "S1"


def test_3_a_leader_is_named_and_no_distribution_keeps_the_given_word(reset_stores):
    from ELINS import ingestion_bus as ib
    import library_store
    lead = {"outputs": {"attractor": "S3", "collapse_state": "soft", "state_distribution": dict(_LEAD)}}
    assert library_store.get(ib.persist_to_library(
        "alice", source="elins_v2_view", region=None, raw_text="t", envelope=lead,
    ))["title"] == "[elins_v2_view] S3 / soft"
    legacy = {"outputs": {"attractor": "S2", "collapse_state": "soft"}}   # no distribution at all
    assert library_store.get(ib.persist_to_library(
        "alice", source="feed:x", region="us", raw_text="t", envelope=legacy,
    ))["title"].startswith("[feed:x] S2 / soft")
    # a caller-supplied title still replaces the generated one (#138)
    assert library_store.get(ib.persist_to_library(
        "alice", source="elins_v2_view", region=None, raw_text="t",
        envelope={"outputs": {"attractor": "S1", "collapse_state": "soft",
                              "state_distribution": dict(_LEVEL)}},
        title="the run I kept",
    ))["title"] == "the run I kept"


def test_3_the_kernel_write_agrees_with_the_rule_for_a_real_envelope(reset_stores):
    """End to end through run_manual_ingestion: whatever the engine's own
    distribution is for this text, the title names what the surface would
    show for it -- a state word or "indeterminate" -- never the bare argmax
    of a tie."""
    from ELINS import elins_v2_view as v
    import intelligence_kernel as ik
    import library_store
    out = ik.run_manual_ingestion(
        "alice", "we agreed on the terms and then nothing was said for weeks",
        source="elins_v2_view",
    )
    row = library_store.get(out["library_id"])
    outputs = row["metadata"]["envelope"]["outputs"]
    assert outputs["attractor"] in {"S1", "S2", "S3", "S4"}            # wire unchanged
    verdict = v.attractor_verdict(outputs["state_distribution"], outputs["attractor"])
    expected = verdict["state"] if verdict["determinate"] else v.INDETERMINATE_ATTRACTOR
    assert row["title"] == f"[elins_v2_view] {expected} / {outputs['collapse_state']}"
