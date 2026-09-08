"""
#114 -- the five bearings into the seal · #109 temperature 0 · #166e the
flatten branch left alone.

WHAT THESE PIN. The physics call runs at temperature 0. A physics run with
a thread seals its five enum strings + run id onto ITS OWN turn: "unclear"
is kept, a missing key is OMITTED (never "" / {} / a default), a prose
value is skipped, an empty layer writes no bearings key and says why, and
a text-only turn never gains one. The header is the modal value over the
last 3 turns that have bearings ({value, of_n}; a tie reads "split"; fewer
than 3 reads "of n"; none -> None), with age in TURNS, never a clock. The
turns route serves it; the thread turn path still makes no model call.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import json  # noqa: E402
import secrets  # noqa: E402
import time  # noqa: E402

import bcrypt  # noqa: E402
import pytest  # noqa: E402

import intelligence_kernel as ik  # noqa: E402
import memory_vault  # noqa: E402
import model_router as mr  # noqa: E402
import threads_vault  # noqa: E402
import turn_record as tr  # noqa: E402

U = "u_bearings"
T = "thread_b1"

LAYER = {"trust": "low", "alignment": "misaligned", "boundary": "contested",
         "agency": "constrained", "distance": "increasing"}


def _physics(layer=LAYER, ts_ms=1_788_000_000_000):
    return {"field_curvature": {}, "edge_pressure": {}, "relational_primitives": dict(layer),
            "external_expression": {}, "_meta": {"model_id": "m", "ts_ms": ts_ms, "parse_error": None}}


@pytest.fixture(autouse=True)
def _clean(reset_stores):
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    yield


# --------------------------------------------------------------------------
# #109 -- temperature 0
# --------------------------------------------------------------------------
def test_109_the_physics_call_runs_at_temperature_zero(monkeypatch):
    calls = []

    def fake(model_id, prompt, **kw):
        calls.append(kw)
        return {"ok": True, "text": json.dumps({
            "field_curvature": {"a": 1}, "edge_pressure": {"b": 2},
            "relational_primitives": LAYER, "external_expression": {"c": 3},
        }), "model_id": model_id, "provider": "fake", "mock": True, "ts": 0.0}

    monkeypatch.setattr(mr, "route_request", fake)
    out = ik.run_emotional_physics("alice", "a situation with a deadline")
    assert calls and calls[0].get("temperature") == 0.0
    assert out["relational_primitives"] == LAYER


# --------------------------------------------------------------------------
# the seal
# --------------------------------------------------------------------------
def test_the_five_enum_strings_and_the_run_id_land_on_the_runs_own_turn():
    key = tr.record_turn(U, T, "the ridge is contested")["sealed_key"]
    r = tr.seal_physics_bearings(U, T, key, _physics(), run_id=1_788_000_000_000)
    assert r["sealed"] is True
    rec = memory_vault.vault_get(U, key)
    assert rec["bearings"] == LAYER
    assert rec["run_id"] == 1_788_000_000_000
    # the seal's own halves are untouched
    assert rec["expectation"] and rec["observation"] is None and rec["class"] == "geometry"


def test_unclear_is_a_value_and_is_kept():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    tr.seal_physics_bearings(U, T, key, _physics({**LAYER, "trust": "unclear"}), run_id=1)
    assert memory_vault.vault_get(U, key)["bearings"]["trust"] == "unclear"


def test_a_missing_bearing_is_omitted_never_defaulted():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    layer = {"trust": "high", "boundary": "clear"}                # three keys absent
    tr.seal_physics_bearings(U, T, key, _physics(layer), run_id=1)
    b = memory_vault.vault_get(U, key)["bearings"]
    assert b == {"trust": "high", "boundary": "clear"}
    for k in ("alignment", "agency", "distance"):
        assert k not in b
    assert "" not in b.values() and {} not in b.values()


def test_prose_is_not_a_bearing_and_is_skipped():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    layer = {**LAYER, "distance": "the distance is growing week by week"}
    r = tr.seal_physics_bearings(U, T, key, _physics(layer), run_id=1)
    assert r["sealed"] is True and r["skipped"] == ["distance"]
    b = memory_vault.vault_get(U, key)["bearings"]
    assert "distance" not in b and b["trust"] == "low"


def test_a_token_outside_the_vocabulary_is_not_a_bearing():
    """A refuter's catch: the model writes these, and a steered model could
    emit a whitespace-free sentence that _reject_prose alone would pass."""
    key = tr.record_turn(U, T, "t")["sealed_key"]
    layer = {**LAYER, "trust": "she_threatened_to_take_the_kids", "agency": "MISALIGNED"}
    r = tr.seal_physics_bearings(U, T, key, _physics(layer), run_id=1)
    assert r["sealed"] is True and sorted(r["skipped"]) == ["agency", "trust"]
    b = memory_vault.vault_get(U, key)["bearings"]
    assert "trust" not in b and "agency" not in b and b["alignment"] == "misaligned"
    # case is normalised: the vocabulary is matched lowercase
    r = tr.seal_physics_bearings(U, T, key, _physics({"alignment": "MISALIGNED"}), run_id=1)
    assert memory_vault.vault_get(U, key)["bearings"] == {"alignment": "misaligned"}


def test_the_vocabulary_is_the_prompts_own_layer_3():
    """Drift guard: PHYSICS_BEARING_VOCAB must equal the enum block the kernel
    prompt names for LAYER 3, bearing by bearing."""
    import re
    block = ik._EMOTIONAL_PHYSICS_PROMPT.split("LAYER 3", 1)[1].split("dominant_pattern", 1)[0]
    found = {m.group(1): frozenset(w.strip() for w in m.group(2).split("|"))
             for m in re.finditer(r'"(\w+)":\s*"([a-z_ |]+)"', block)}
    assert set(found) == set(tr.PHYSICS_BEARINGS)
    for b in tr.PHYSICS_BEARINGS:
        assert found[b] == tr.PHYSICS_BEARING_VOCAB[b], b


def test_run_id_is_omitted_when_the_run_has_none():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    tr.seal_physics_bearings(U, T, key, _physics(), run_id=None)
    rec = memory_vault.vault_get(U, key)
    assert rec["bearings"] == LAYER and "run_id" not in rec


def test_an_empty_layer_writes_no_bearings_key_and_says_why():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    for layer in ({}, None):
        r = tr.seal_physics_bearings(U, T, key, _physics(layer) if layer is not None else {"_meta": {}}, run_id=1)
        assert r["sealed"] is False and "absent" in r["reason"]
    rec = memory_vault.vault_get(U, key)
    assert "bearings" not in rec and "run_id" not in rec


def test_all_prose_writes_nothing_and_names_the_skipped():
    key = tr.record_turn(U, T, "t")["sealed_key"]
    r = tr.seal_physics_bearings(U, T, key, _physics({"trust": "very low indeed"}), run_id=1)
    assert r["sealed"] is False and r["skipped"] == ["trust"]
    assert "bearings" not in memory_vault.vault_get(U, key)


def test_a_text_only_turn_has_no_bearings_key():
    key = tr.record_turn(U, T, "just text")["sealed_key"]
    rec = memory_vault.vault_get(U, key)
    assert "bearings" not in rec and "run_id" not in rec


def test_a_seal_onto_another_threads_turn_is_refused():
    key = tr.record_turn(U, "other_thread", "t")["sealed_key"]
    with pytest.raises(ValueError):
        tr.seal_physics_bearings(U, T, key, _physics(), run_id=1)
    with pytest.raises(KeyError):
        tr.seal_physics_bearings(U, T, tr._thread_ns(T) + "nope", _physics(), run_id=1)


def test_the_scorer_and_trust_signal_ignore_the_bearings_key():
    k0 = tr.record_turn(U, T, "the ridge is contested")["sealed_key"]
    tr.seal_physics_bearings(U, T, k0, _physics(), run_id=1)
    tr.record_turn(U, T, "the ridge is held")          # observes k0
    rows = tr.list_turn_records(U, T)
    assert tr.score_record(rows[0])["status"] == "scored"
    assert tr.trust_signal(U, T)["status"] in ("value", "undefined")


# --------------------------------------------------------------------------
# the header
# --------------------------------------------------------------------------
def _rows(*bearings_per_turn):
    rows = []
    for i, b in enumerate(bearings_per_turn):
        r = {"turn_index": i, "ts_sealed": i, "expectation": {"source": "persistence"}, "observation": None}
        if b is not None:
            r["bearings"] = b
        rows.append(r)
    return rows


def test_header_three_agree():
    h = tr.bearings_header(_rows({"trust": "low"}, {"trust": "low"}, {"trust": "low"}))
    assert h["trust"] == {"value": "low", "count": 3, "of_n": 3}
    assert h["age"] == {"sealed_turn": 2, "now_turn": 2}


def test_header_two_of_three():
    h = tr.bearings_header(_rows({"trust": "low"}, {"trust": "high"}, {"trust": "low"}))
    assert h["trust"] == {"value": "low", "count": 2, "of_n": 3}


def test_header_split_on_a_tie():
    h = tr.bearings_header(_rows({"trust": "low"}, {"trust": "high"}, {"trust": "medium"}))
    assert h["trust"] == {"value": "split", "count": 1, "of_n": 3}
    h = tr.bearings_header(_rows({"trust": "low"}, {"trust": "high"}))
    assert h["trust"] == {"value": "split", "count": 1, "of_n": 2}


def test_header_of_n_below_three_and_a_bearing_none_carried_is_absent():
    h = tr.bearings_header(_rows({"trust": "low", "boundary": "clear"}, None, {"trust": "low"}))
    assert h["trust"] == {"value": "low", "count": 2, "of_n": 2}
    assert h["boundary"] == {"value": "clear", "count": 1, "of_n": 1}
    assert "agency" not in h and "distance" not in h and "alignment" not in h
    # age: the newest turn with bearings is 2, the newest turn is 2
    assert h["age"] == {"sealed_turn": 2, "now_turn": 2}


def test_header_reads_only_the_last_three_with_bearings_and_ages_in_turns():
    rows = _rows({"trust": "high"}, {"trust": "high"}, {"trust": "low"}, {"trust": "low"}, {"trust": "low"}, None, None)
    h = tr.bearings_header(rows)
    assert h["trust"] == {"value": "low", "count": 3, "of_n": 3}   # the first two highs are outside the window
    assert h["age"] == {"sealed_turn": 4, "now_turn": 6}        # two text-only turns since the last seal


def test_header_none_when_no_turn_carries_bearings():
    assert tr.bearings_header(_rows(None, None)) is None
    assert tr.bearings_header([]) is None


# --------------------------------------------------------------------------
# the routes
# --------------------------------------------------------------------------
from conftest import TestClient  # noqa: E402
import app as appmod  # noqa: E402
import sessions_store  # noqa: E402
import users_store  # noqa: E402

client = TestClient(appmod.app)


def _session(user: str) -> dict:
    users_store.create_user(
        username=user, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.update_user(user, {"cohort": "terrace_1"})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _install_fake_handler(monkeypatch, layer=LAYER):
    captured = {"temperature": None, "calls": 0}

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        captured["temperature"] = temperature
        captured["calls"] += 1
        return {"ok": True, "model_id": model_id, "provider": "anthropic",
                "text": json.dumps({"field_curvature": {"a": 1}, "edge_pressure": {"b": 2},
                                    "relational_primitives": dict(layer), "external_expression": {"c": 3}}),
                "mock": False, "ts": 0.0}

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", fake_handler)
    return captured


def test_a_physics_run_with_a_thread_seals_five_strings_and_a_run_id_onto_its_turn(monkeypatch):
    captured = _install_fake_handler(monkeypatch)
    h = _session("b_alice")
    tid = threads_vault.create_thread("b_alice", "rel", project_id="relationships")["thread_id"]
    r = client.post("/me/emotional_physics/analyze", headers=h,
                    json={"text": "the ridge is contested and the pressure is rising", "thread_id": tid, "surface": "personal"})
    assert r.status_code == 200, r.text[:200]
    assert captured["temperature"] == 0.0                      # #109, on the wire
    run_id = r.json()["_meta"]["ts_ms"]
    body = client.get("/me/relationships/%s/turns" % tid, headers=h).json()
    assert body["turn_count"] == 1
    turn = body["turns"][0]
    assert turn["bearings"] == LAYER and turn["run_id"] == run_id
    assert all(isinstance(v, str) for v in turn["bearings"].values())
    assert body["bearings_header"]["trust"] == {"value": "low", "count": 1, "of_n": 1}
    assert body["bearings_header"]["age"] == {"sealed_turn": 0, "now_turn": 0}


def test_a_run_that_seals_nothing_leaves_a_trace_in_the_log(monkeypatch, caplog):
    """A refuter's catch: the seal returned its reason and the route threw it
    away. Now the reason and the NAMES of skipped bearings are logged --
    never a value, never an id."""
    import logging

    def bad_handler(model_id, prompt, *, temperature, max_tokens):
        return {"ok": True, "model_id": model_id, "provider": "anthropic",
                "text": "not json at all", "mock": False, "ts": 0.0}

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", bad_handler)
    caplog.set_level(logging.INFO, logger="clarityos")
    h = _session("b_erin")
    tid = threads_vault.create_thread("b_erin", "rel", project_id="relationships")["thread_id"]
    r = client.post("/me/emotional_physics/analyze", headers=h, json={"text": "a run", "thread_id": tid})
    assert r.status_code == 200 and r.json()["_meta"]["parse_error"]
    lines = [rec.getMessage() for rec in caplog.records if "physics bearings not sealed" in rec.getMessage()]
    assert lines and "relational_primitives absent" in lines[0]
    assert tid not in lines[0] and "b_erin" not in lines[0]
    body = client.get("/me/relationships/%s/turns" % tid, headers=h).json()
    assert "bearings" not in body["turns"][0] and body["bearings_header"] is None


def test_a_text_only_run_has_no_bearings_key_and_the_header_reads_none():
    h = _session("b_bob")
    tid = threads_vault.create_thread("b_bob", "rel", project_id="relationships")["thread_id"]
    r = client.post("/elins/v2/run", headers=h, json={"input": {"raw_text": "the ridge is contested"}, "thread_id": tid})
    assert r.status_code == 200, r.text[:200]
    body = client.get("/me/relationships/%s/turns" % tid, headers=h).json()
    assert body["turn_count"] == 1 and "bearings" not in body["turns"][0] and "run_id" not in body["turns"][0]
    assert body["bearings_header"] is None


def test_the_header_is_a_modal_over_physics_turns_and_ages_past_text_only_turns(monkeypatch):
    _install_fake_handler(monkeypatch, {**LAYER, "trust": "low"})
    h = _session("b_carol")
    tid = threads_vault.create_thread("b_carol", "rel", project_id="relationships")["thread_id"]
    for _ in range(2):
        assert client.post("/me/emotional_physics/analyze", headers=h,
                           json={"text": "a run", "thread_id": tid}).status_code == 200
    _install_fake_handler(monkeypatch, {**LAYER, "trust": "high"})
    assert client.post("/me/emotional_physics/analyze", headers=h,
                       json={"text": "a run", "thread_id": tid}).status_code == 200
    # two text-only turns after the last physics run
    for _ in range(2):
        assert client.post("/elins/v2/run", headers=h,
                           json={"input": {"raw_text": "text only"}, "thread_id": tid}).status_code == 200
    body = client.get("/me/relationships/%s/turns" % tid, headers=h).json()
    hd = body["bearings_header"]
    assert hd["trust"] == {"value": "low", "count": 2, "of_n": 3}          # 2 of 3
    assert hd["boundary"] == {"value": "contested", "count": 3, "of_n": 3}
    assert hd["age"] == {"sealed_turn": 2, "now_turn": 4}      # turns, never a clock


def test_the_thread_turn_path_makes_no_model_call_for_physics(monkeypatch):
    """The member's chat turn seals a text-only record; physics never runs
    on that path (the standing prohibition)."""
    calls = []
    monkeypatch.setattr(mr, "route_request", lambda model_id, prompt, **kw: (calls.append(kw) or {
        "ok": True, "text": "a reply", "model_id": model_id, "provider": "fake", "mock": True, "ts": 0.0}))
    tid = threads_vault.create_thread("b_dave", title="t")["thread_id"]
    ik.run_thread_message("b_dave", tid, "hello there")
    assert len(calls) == 1 and "temperature" not in calls[0]   # the chat call only, router default
    rows = tr.list_turn_records("b_dave", tid)
    assert rows and "bearings" not in rows[-1]
