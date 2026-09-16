"""
#303 · #304 · #305 · #306 · #307 -- seal what reads, count what counts.

WHAT THESE PIN (backend half; the render half is under web/src).

A2  counsel {message_guidance, friction_reduction_moves, next_step} is FOLDED
    under external_expression.counsel -- kept for router contracts and
    scoring, never dropped; absent when none arrived (D5).
A3  _meta.ring: "meaning" on a physics reply (a model read), "event" on an
    ELINS envelope (the counters counted).
A4  a PERSONAL run names whose field it reads (author | addressee |
    observer); absent -> 400 whose_field_required; "instrument" and any
    other word -> 400 whose_field_refused, the word never echoed; refused
    BEFORE a turn is recorded or a model called; an accepted word is stored
    on the turn and served by /me/relationships/{id}/turns; the thread
    surface is not asked.
A5  scrub_credentials, extended: e-mails, phones and the member name list
    become class tokens; a date, a count, a timestamp are never eaten; the
    physics prose on the wire is scrubbed with the member's names.
B   a summary's meta carries the model that wrote it and the window facts
    of the one cut (chars of the whole thread, messages a-b of c); cleared
    with the summary; on the wire.
D   a parse MISS reports _meta.raw_len and _meta.refusal_shape -- two facts
    about the text, never the text; absent on a hit.
E1  _meta.n_points on the ELINS wire: scored_turns of the run's relationship
    on the personal surface; 1 anywhere else.
F   #290 -- the operator rollup and the indicator's route exclude
    thread-tagged on-demand records unless that thread is selected; the
    route carries the record's classification beside the mode.
C5  the dashboard section carries no_signal (None until a run exists).
"""
from __future__ import annotations

import copy
import json
import secrets
import time

import pytest
from fastapi import FastAPI

from conftest import TestClient, seed_controller

import el_ins
import intelligence_kernel as ik
import memory_vault
import model_router as mr
import runtime_http as rh
import runtime_privacy
import sessions_store
import threads_vault
import turn_record as tr
import users_store


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean(reset_stores):
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    el_ins._reset_all_for_tests()
    yield
    el_ins._reset_all_for_tests()


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _member(username: str = "member_a"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.update_user(username, {
        "membership_status": "active", "membership_tier": "founding_500",
    })
    seed_controller(username)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


def _relationship(user: str, title: str = "Copilot-me-system_install") -> str:
    return threads_vault.create_thread(user, title, project_id="relationships")["thread_id"]


def _payload() -> dict:
    return {
        "field_curvature": {"intensity": "medium", "gradient_direction": "mixed",
                            "stability": "unstable", "dominant_forces": ["time_pressure"],
                            "notes": "split between two roles"},
        "edge_pressure": {"signal_clarity": "mixed", "signal_intensity": "medium",
                          "coherence": "fragmented", "perceived_posture": ["ambivalent"],
                          "risk_of_misread": "high", "notes": "may read as distant"},
        "relational_primitives": {"trust": "fluctuating", "alignment": "partially_aligned",
                                  "boundary": "soft", "agency": "partial", "distance": "increasing",
                                  "dominant_pattern": ["boundary_uncertainty"],
                                  "notes": "boundary needs naming"},
        "external_expression": {"recommended_posture": ["clarify_intent", "set_boundary"],
                                "message_guidance": ["state the constraint plainly"],
                                "friction_reduction_moves": ["propose a single next checkpoint"],
                                "risk_if_unchanged": "drift continues",
                                "next_step": "send a 3-line clarification"},
    }


def _fake_anthropic(monkeypatch, response_text: str):
    captured = {"prompt": None, "calls": 0}

    def handler(model_id, prompt, *, temperature, max_tokens):
        captured["prompt"] = prompt
        captured["calls"] += 1
        return {"ok": True, "model_id": model_id, "provider": "anthropic",
                "text": response_text, "mock": False, "ts": 0.0}

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", handler)
    return captured


def _physics(client, h, **body):
    return client.post("/me/emotional_physics/analyze", headers=h, json={"text": "the ridge is contested", **body})


def _elins(client, h, **body):
    return client.post("/elins/v2/run", headers=h,
                       json={"region": None, "input": {"raw_text": "the ridge is contested and the pressure is rising"}, **body})


# ===========================================================================
# A2 -- counsel folded, kept
# ===========================================================================
def test_a2_counsel_is_folded_under_external_expression_and_never_dropped(monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    out = ik.run_emotional_physics("alice", "i feel stuck between two roles")
    ext = out["external_expression"]
    for k in ik.PHYSICS_COUNSEL_KEYS:
        assert k not in ext, k
    assert ext["counsel"] == {
        "message_guidance": ["state the constraint plainly"],
        "friction_reduction_moves": ["propose a single next checkpoint"],
        "next_step": "send a 3-line clarification",
    }
    # the projection and the scored array stay where they were
    assert ext["risk_if_unchanged"] == "drift continues"
    assert ext["recommended_posture"] == ["clarify_intent", "set_boundary"]
    # scoring reads the same count before and after the fold
    before = ik._count_substantive_fields(_payload())
    assert ik._count_substantive_fields({k: out[k] for k in ik._EMOTIONAL_PHYSICS_KEYS}) == before


def test_a2_counsel_is_absent_not_empty_when_none_arrived(monkeypatch):
    p = _payload()
    for k in ik.PHYSICS_COUNSEL_KEYS:
        p["external_expression"].pop(k)
    _fake_anthropic(monkeypatch, json.dumps(p))
    out = ik.run_emotional_physics("alice", "text")
    assert "counsel" not in out["external_expression"]


# ===========================================================================
# A3 -- the ring
# ===========================================================================
def test_a3_physics_is_the_meaning_ring_and_elins_the_event_ring(client, monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    r = _physics(client, h, surface="thread")
    assert r.status_code == 200, r.text
    assert r.json()["_meta"]["ring"] == ik.RING_MEANING == "meaning"
    e = _elins(client, h, surface="thread")
    assert e.status_code == 200, e.text
    assert e.json()["_meta"]["ring"] == ik.RING_EVENT == "event"
    assert e.json()["_meta"]["n_points"] == 1          # E1: the thread surface is one read


# ===========================================================================
# A4 -- whose field
# ===========================================================================
def test_a4_a_personal_run_without_whose_field_is_refused_before_record_or_model(client, monkeypatch, app_module):
    captured = _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    tid = _relationship(user)
    r = _physics(client, h, surface="personal", thread_id=tid)
    assert r.status_code == 400
    body = r.json()
    body = body.get("detail", body)
    assert body["error"] == "whose_field_required"
    assert body["message"] == app_module.WHOSE_FIELD_REQUIRED_MSG
    assert captured["calls"] == 0                                   # no model call
    assert client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turn_count"] == 0
    # the ELINS half of the pair is refused by the same door
    e = _elins(client, h, surface="personal", thread_id=tid)
    assert e.status_code == 400
    assert e.json().get("detail", e.json())["error"] == "whose_field_required"


@pytest.mark.parametrize("word,code,msg_attr", [
    ("instrument", "whose_field_refused", "WHOSE_FIELD_INSTRUMENT_MSG"),
    ("Instrument", "whose_field_refused", "WHOSE_FIELD_INSTRUMENT_MSG"),
    ("the lawyer of record", "whose_field_refused", "WHOSE_FIELD_UNKNOWN_MSG"),
])
def test_a4_instrument_and_unknown_words_are_refused_and_never_echoed(client, monkeypatch, app_module, word, code, msg_attr):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    r = _physics(client, h, surface="personal", whose_field=word)
    assert r.status_code == 400
    body = r.json().get("detail", r.json())
    assert body["error"] == code
    assert body["message"] == getattr(app_module, msg_attr)
    assert "whose_field" not in body["message"]                    # #237: no internal key on glass
    if word != "instrument":
        assert word not in r.text


def test_a4_an_accepted_field_is_stored_on_the_turn_and_served_raw(client, monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    tid = _relationship(user)
    assert _physics(client, h, surface="personal", thread_id=tid, whose_field="author").status_code == 200
    assert _elins(client, h, surface="personal", thread_id=tid, whose_field="observer").status_code == 200
    turns = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turns"]
    assert [t.get("whose_field") for t in turns] == ["author", "observer"]
    # a run that carried none has NO key, never ""
    assert _elins(client, h, surface="thread", thread_id=tid).status_code == 200
    last = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turns"][-1]
    assert "whose_field" not in last


def test_a4_the_thread_surface_is_not_asked(client, monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    assert _physics(client, h, surface="thread").status_code == 200
    assert _physics(client, h).status_code == 200                      # default surface = thread


# ===========================================================================
# A5 -- prose scrubbed
# ===========================================================================
@pytest.mark.parametrize("raw,names,expect", [
    ("write to jane.doe@example.com today", None, "write to [email] today"),
    ("call 555-123-4567 or (555) 123-4567 or +44 20 7946 0958", None, "call [phone] or [phone] or [phone]"),
    ("ring +1 (555) 123-4567; filed +1 2026-09-16; ext 10-15", None, "ring [phone]; filed +1 2026-09-16; ext 10-15"),
    ("on 2026-09-16, 8,000 of 12,000 chars, ts 1700000000.0, sha 195a01f", None,
     "on 2026-09-16, 8,000 of 12,000 chars, ts 1700000000.0, sha 195a01f"),
    ("Chris said it; chris again; Christopher did not; me too", ["Chris", "me"],
     "[name] said it; [name] again; Christopher did not; me too"),
    ("key at https://x.y/?key=abc and sk-abcdefghijklmnop", None, "key at [url] and [redacted]"),
])
def test_a5_scrub_credentials_extended(raw, names, expect):
    assert runtime_privacy.scrub_credentials(raw, names) == expect


def test_a5_scrub_prose_walks_the_body_and_keeps_shape():
    body = {"a": {"notes": "mail bob@example.com", "list": ["Ann called 555-123-4567", 3, None, ""]}, "n": 1}
    out = runtime_privacy.scrub_prose(body, names=["Ann"])
    assert out == {"a": {"notes": "mail [email]", "list": ["[name] called [phone]", 3, None, ""]}, "n": 1}
    assert body["a"]["notes"] == "mail bob@example.com"               # the input is not mutated


def test_a5_the_physics_prose_on_the_wire_is_scrubbed_with_the_member_names(client, monkeypatch):
    p = _payload()
    # the name list = the account's local part + the relationship's title as ONE
    # phrase; a word of the title on its own ("Copilot") is not a name.
    p["field_curvature"]["notes"] = ("Copilot-me-system_install wrote to member_a at member_a@example.com; "
                                     "call 555-123-4567; Copilot alone stays")
    p["external_expression"]["risk_if_unchanged"] = "Copilot-me-system_install drifts"
    p["external_expression"]["next_step"] = "ring 555-123-4567"
    _fake_anthropic(monkeypatch, json.dumps(p))
    user, h = _member("member_a")
    tid = _relationship(user, title="Copilot-me-system_install")
    r = _physics(client, h, surface="personal", thread_id=tid, whose_field="author")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["field_curvature"]["notes"] == "[name] wrote to [name] at [email]; call [phone]; Copilot alone stays"
    assert body["external_expression"]["risk_if_unchanged"] == "[name] drifts"
    assert body["external_expression"]["counsel"]["next_step"] == "ring [phone]"
    assert "member_a@example.com" not in r.text and "555-123-4567" not in r.text
    assert body["relational_primitives"]["trust"] == "fluctuating"       # enums untouched


def test_a5_the_name_list_is_the_title_as_one_phrase_and_an_enum_is_never_a_name(client, monkeypatch):
    """A refuter's catch: split title words made "the" and "high" names, and a
    title word that spells an enum member turned a bearing into "[name]"
    before the #114 seal read it. The list is the title as ONE phrase and the
    name pass runs on prose leaves only."""
    p = _payload()
    p["relational_primitives"]["trust"] = "low"
    p["field_curvature"]["stability"] = "stable"
    p["field_curvature"]["notes"] = "the high road wrote; low trust; the road is stable"
    p["external_expression"]["risk_if_unchanged"] = "the high road drifts"
    _fake_anthropic(monkeypatch, json.dumps(p))
    user, h = _member("member_a")
    tid = _relationship(user, title="the high road")
    r = _physics(client, h, surface="personal", thread_id=tid, whose_field="author")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["relational_primitives"]["trust"] == "low"
    assert body["field_curvature"]["stability"] == "stable"
    assert body["field_curvature"]["notes"] == "[name] wrote; low trust; the road is stable"
    assert body["external_expression"]["risk_if_unchanged"] == "[name] drifts"
    # the seal read the enum, not "[name]"
    turn = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turns"][-1]
    assert turn["bearings"]["trust"] == "low"


def test_a5_scrub_prose_names_only_under_prose_keys():
    body = {"a": {"trust": "low", "notes": "low says hi to bob@example.com", "counsel": {"next_step": "call low"}},
            "b": "low"}
    out = runtime_privacy.scrub_prose(body, names=["low"], prose_keys=("notes", "counsel"))
    assert out == {"a": {"trust": "low", "notes": "[name] says hi to [email]", "counsel": {"next_step": "call [name]"}},
                   "b": "low"}
    # no prose_keys: the #284 behaviour, names everywhere
    assert runtime_privacy.scrub_prose({"x": "low"}, names=["low"]) == {"x": "[name]"}


# ===========================================================================
# B -- the summary's model + window facts
# ===========================================================================
def _thread_with(user: str, contents: list[str]) -> str:
    tid = threads_vault.create_thread(user, "chat")["thread_id"]
    for i, c in enumerate(contents):
        threads_vault.append_message(user, tid, {"role": "user" if i % 2 == 0 else "assistant", "content": c})
    return tid


def test_b_summary_window_arithmetic_is_a_suffix_of_the_whole_thread():
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": ("%02d" % i) + "x" * 598} for i in range(30)]
    prompt, facts = ik._summary_window(msgs)
    lines = [f"{m['role']}: {m['content']}" for m in msgs]
    full = "\n".join(lines)
    assert facts["summary_total_chars"] == len(full)
    assert facts["summary_total_messages"] == 30
    assert facts["summary_window_last_message"] == 30
    assert facts["summary_window_chars"] < ik.SUMMARY_CONTEXT_CHAR_BUDGET
    # the transcript inside the fences is exactly the last window_chars of the whole
    inner = prompt.split(ik.SUMMARY_FENCE_OPEN + "\n", 1)[1].rsplit("\n" + ik.SUMMARY_FENCE_CLOSE, 1)[0]
    assert inner == full[-facts["summary_window_chars"]:]
    # the first message touched, by independent arithmetic
    start = len(full) - facts["summary_window_chars"]
    ends, cum = [], 0
    for i, line in enumerate(lines):
        cum += (0 if i == 0 else 1) + len(line)
        ends.append(cum)
    assert facts["summary_window_first_message"] == next(i + 1 for i, e in enumerate(ends) if e > start)
    assert 1 < facts["summary_window_first_message"] <= 30


def test_b_a_short_thread_reads_whole():
    _, facts = ik._summary_window([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert facts == {"summary_window_chars": len("user: hi\nassistant: hello"), "summary_total_chars": len("user: hi\nassistant: hello"),
                     "summary_total_messages": 2, "summary_window_first_message": 1, "summary_window_last_message": 2}


def test_b_the_meta_carries_model_and_window_and_clears_with_the_summary(client, monkeypatch):
    _fake_anthropic(monkeypatch, "A two-line summary of the thread.")
    user, h = _member()
    tid = _thread_with(user, ["draft the kickoff doc", "sure", "and the budget"])
    r = client.post(f"/me/threads/{tid}/summarize", headers=h, json={"force": True})
    assert r.status_code == 200, r.text
    meta = r.json()["meta"]
    assert meta["summary_model_id"] == mr.TASK_DEFAULTS["thread_summary"]
    assert meta["summary_total_messages"] == 3
    assert meta["summary_window_first_message"] == 1 and meta["summary_window_last_message"] == 3
    assert meta["summary_window_chars"] == meta["summary_total_chars"] == len("user: draft the kickoff doc\nassistant: sure\nuser: and the budget")
    g = client.get(f"/me/threads/{tid}/summary", headers=h).json()["meta"]
    assert {k: g[k] for k in threads_vault.SUMMARY_WINDOW_KEYS} == {k: meta[k] for k in threads_vault.SUMMARY_WINDOW_KEYS}
    # cleared with the summary
    cleared = threads_vault.update_thread_summary(user, tid, None, 1)
    assert cleared["summary_model_id"] is None
    assert all(cleared[k] is None for k in threads_vault.SUMMARY_WINDOW_KEYS)


def test_b_a_row_that_predates_the_stamp_reads_none_on_the_wire(client):
    user, h = _member()
    tid = _thread_with(user, ["x"])
    meta = client.get(f"/me/threads/{tid}/summary", headers=h).json()["meta"]
    assert meta["summary_model_id"] is None
    assert all(meta[k] is None for k in threads_vault.SUMMARY_WINDOW_KEYS)


# ===========================================================================
# D -- a parse miss: two facts, never the text
# ===========================================================================
@pytest.mark.parametrize("text,shape", [
    ("I can't help with this request. It asks me to profile a person.", True),
    ("lorem ipsum dolor sit amet, no braces anywhere", False),
])
def test_d_a_parse_miss_reports_raw_len_and_refusal_shape_never_the_text(client, monkeypatch, text, shape):
    _fake_anthropic(monkeypatch, text)
    user, h = _member()
    r = _physics(client, h, surface="thread")
    assert r.status_code == 200
    m = r.json()["_meta"]
    assert m["parse_error"]
    assert m["raw_len"] == len(text)
    assert m["refusal_shape"] is shape
    assert text not in r.text and text[:20] not in r.text


def test_d_a_parse_hit_carries_neither_fact(monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    m = ik.run_emotional_physics("alice", "text")["_meta"]
    assert "raw_len" not in m and "refusal_shape" not in m


# ===========================================================================
# E1 -- n_points
# ===========================================================================
def test_e1_n_points_is_the_relationships_scored_turns_on_the_personal_surface(client, monkeypatch):
    _fake_anthropic(monkeypatch, json.dumps(_payload()))
    user, h = _member()
    tid = _relationship(user)
    for _ in range(2):
        assert _physics(client, h, surface="personal", thread_id=tid, whose_field="author").status_code == 200
        e = _elins(client, h, surface="personal", thread_id=tid, whose_field="author")
        assert e.status_code == 200
        sig = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["trust_signal"]
        assert e.json()["_meta"]["n_points"] == sig["scored_turns"]
    assert e.json()["_meta"]["n_points"] >= 2
    # no relationship: one read, said honestly
    assert _elins(client, h, surface="personal", whose_field="author").json()["_meta"]["n_points"] == 1


# ===========================================================================
# F -- #290 the operator's default scope
# ===========================================================================
def _mk(cls: str, el: float, ins: float) -> dict:
    return {"analysis": {"el_components": [], "ins_components": [], "el_score": el, "ins_score": ins,
                         "ratio_classification": cls},
            "reasoning_mode": "normal",
            "regression_chain": {"projection": None, "drivers": [], "precedents": [], "principle_stack": [], "invariant": None},
            "stability_notes": None}


def _store(op: str, ts: float, cls: str, thread_id, source: str):
    el_ins.store_el_ins_record({"operator_id": op, "thread_id": thread_id, "timestamp": ts,
                                "source": source, "result": _mk(cls, 4.0, 4.0)})


@pytest.fixture
def op_client():
    app = FastAPI()
    app.include_router(rh.el_ins_router)
    yield TestClient(app)


def _op_auth(user: str = "op_alice") -> dict:
    sid = f"auth-303-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def test_f_scope_default_keeps_per_turn_and_untagged_drops_tagged_on_demand_unless_selected():
    rows = [{"thread_id": "t1", "source": "on_demand"}, {"thread_id": None, "source": "on_demand"},
            {"thread_id": "t1", "source": "per_turn"}, {"thread_id": "t2", "source": "on_demand"}]
    assert el_ins.scope_default(rows) == rows[1:3]
    assert el_ins.scope_default(rows, "t1") == rows[:3]


def test_f_the_rollup_excludes_thread_tagged_on_demand_unless_that_thread_is_selected(op_client):
    now = time.time()
    _store("op_alice", now - 30, "balanced", "t1", "on_demand")
    _store("op_alice", now - 20, "balanced", None, "on_demand")
    _store("op_alice", now - 10, "balanced", "t1", "per_turn")
    assert el_ins.compute_rollup("op_alice", "24h")["record_count"] == 2
    assert el_ins.compute_rollup("op_alice", "24h", thread_id="t1")["record_count"] == 3
    h = _op_auth()
    assert op_client.get("/el_ins/rollup/24h", headers=h).json()["record_count"] == 2
    assert op_client.get("/el_ins/rollup/24h?thread_id=t1", headers=h).json()["record_count"] == 3


def test_f_the_indicator_route_reads_the_default_scope_and_names_the_record(op_client):
    _store("op_alice", 1700000000.0, "balanced", None, "on_demand")
    _store("op_alice", 1700000010.0, "high_el", "t1", "on_demand")           # newest, thread-tagged
    h = _op_auth()
    body = op_client.get("/el_ins/operator/reasoning_mode", headers=h).json()
    assert body["ratio_classification"] == "balanced" and body["thread_id"] is None and body["source"] == "on_demand"
    sel = op_client.get("/el_ins/operator/reasoning_mode?thread_id=t1", headers=h).json()
    assert sel["ratio_classification"] == "high_el" and sel["thread_id"] == "t1"
    empty = op_client.get("/el_ins/operator/reasoning_mode", headers=_op_auth("op_nobody")).json()
    assert empty["ratio_classification"] is None and empty["reasoning_mode"] == "normal"


# ===========================================================================
# C5 -- the dashboard section says no_signal
# ===========================================================================
def test_c5_dashboard_section_carries_no_signal():
    import elins_dashboard as d
    assert d._empty_section()["no_signal"] is None
    zeros = {k: 0.0 for k in ("pressure", "tension", "trust", "drift", "contradiction", "alignment")}
    rec = {"elins": {"synthesis": {"no_signal": True}, "primitives": {"intensities": zeros}}}
    assert d._section_from_run(rec, day="2026-09-16")["no_signal"] is True
    rec2 = {"elins": {"synthesis": {"no_signal": False}, "primitives": {"intensities": {**zeros, "pressure": 0.1}}}}
    assert d._section_from_run(rec2, day="2026-09-16")["no_signal"] is False
