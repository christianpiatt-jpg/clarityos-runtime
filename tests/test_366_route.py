"""
#366 -- the member route end to end: POST /me/threads/{id}/message carries
the direction bit, composes and reserves on the algebra, sends three lane
prompts that hold no member text and no name, persists the READING as the
reply, records direction · picked · the ask on the seal, writes the
relationship's ledger, routes ``diagnostic`` to the sovereign pin and names
it un-provisioned when a mock answered, and surfaces a halt without a
vendor call.

Every test names the mutation that breaks it.
"""
from __future__ import annotations

import json
import re
import secrets
import time

import pytest

pytest.importorskip("spacy", reason="#366 A1: spaCy is the parser (requirements.txt)")

import app as _app  # noqa: E402
import ep_up_payload  # noqa: E402
import memory_vault  # noqa: E402
import model_router as mr  # noqa: E402
import sessions_store  # noqa: E402
import threads_vault  # noqa: E402
import turn_record  # noqa: E402
import users_store  # noqa: E402
from conftest import TestClient, seed_controller  # noqa: E402

TEXT = "I filed complaints against the agency. The agency dismissed them without a hearing."


class FakeLaneRouter:
    """Answers every lane with well-formed rows read off the payload. Records
    (model_id, prompt) per call. ``local`` models answer as the router's
    mock (no daemon), like model_router._call_local does today."""

    def __init__(self):
        self.calls: list = []

    def __call__(self, model_id, prompt, **kwargs):
        self.calls.append((model_id, prompt))
        lane = prompt.split("lane=", 1)[1].split(" ", 1)[0]
        payload = json.loads(prompt.split("\n\n", 1)[1])
        rows = [{"i": i, "state": "met", "direction": "s->o" if t["ok"] == "seat" else "undefined", "mass": 0.4}
                for i, t in enumerate(payload["EP"]["triples"])]
        if model_id.startswith("local:"):
            return {"ok": True, "model_id": model_id, "provider": "local", "text": "[mock %s] frame" % model_id,
                    "mock": True, "ts": time.time(), "stop_reason": None, "usage": None}
        return {"ok": True, "model_id": model_id, "provider": "fake", "text": json.dumps({"v": "lane.v1", "lane": lane, "rows": rows}),
                "mock": False, "ts": time.time(), "stop_reason": "end_turn",
                "usage": {"prompt_tokens": 40, "completion_tokens": 20}}


@pytest.fixture(autouse=True)
def _isolate(reset_stores, monkeypatch):
    memory_vault._reset_for_tests()
    router = FakeLaneRouter()
    monkeypatch.setattr(mr, "route_request", router)
    # the cascade embeds through Vertex; the route's ordering is under test,
    # not the embed -- keep it deterministic and local
    monkeypatch.setattr(_app, "_run_envelope_cascade", lambda user, text: {"response_shape": {"direction": "stalled", "phase": "none", "risk": "low", "sections": ["constraint", "phase", "operator"]}})
    yield router


@pytest.fixture
def client():
    return TestClient(_app.app)


def _member(username: str = "seat@example.com"):
    import bcrypt
    users_store.create_user(username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                            salt="", tier="free", created_at=time.time())
    users_store.set_membership(username, tier="founding_500", price=50.0, status="active")
    seed_controller(username)
    users_store.update_user(username, {"operator_id": "op_" + secrets.token_urlsafe(12)})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


def _post(client, headers, tid, body):
    h = dict(headers); h["Idempotency-Key"] = secrets.token_hex(8)
    return client.post(f"/me/threads/{tid}/message", json=body, headers=h)


class TestTheRoute:
    def test_the_reply_is_the_reading_and_no_lane_saw_text_or_name(self, client, _isolate):
        """Three lane prompts, each the frame plus the payload; the member's
        sentence, the surface word 'complaints' and the seated name 'agency'
        appear in none; the reply starts with the reading's head and carries
        the v24 shape line; the response names direction/picked/reading.
        Mutation: send _format_thread_context -> the sentence is in a prompt."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        r = _post(client, h, tid, {"content": TEXT})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["assistant_message"]["content"].startswith("reading · relation:")
        assert "field: direction stalled" in body["assistant_message"]["content"]
        assert body["direction"] == "query" and body["picked"] is False and body["sovereign"] is None
        assert body["reading"]["lanes"] == ["time", "ambient", "role"] and body["reading"]["rows"] > 0
        assert body["mock"] is False
        assert [p.split("lane=", 1)[1].split(" ", 1)[0] for _, p in _isolate.calls] == ["time", "ambient", "role"]
        for _, p in _isolate.calls:
            assert p.startswith("[ClarityOS ep-up.v1] lane=")
            assert TEXT not in p and "complaints" not in p and "agency" not in p.lower()
        # the reply never carries a lane's JSON
        assert "\"rows\"" not in body["assistant_message"]["content"]

    def test_the_direction_bit_is_validated_and_lands_on_the_seal(self, client):
        """'hunch' -> 400 bad_input; plan/picked -> carried on the wire and on
        this turn's seal with the ask. Mutation: accept any word, or write
        the direction nowhere."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        bad = _post(client, h, tid, {"content": TEXT, "direction": "hunch"})
        assert bad.status_code == 400
        assert (bad.json().get("detail", bad.json()) or {}).get("error") == "bad_input"
        ok = _post(client, h, tid, {"content": TEXT, "direction": "plan", "picked": True})
        assert ok.status_code == 200, ok.text
        assert ok.json()["direction"] == "plan" and ok.json()["picked"] is True
        recs = turn_record.list_turn_records(user, tid)
        assert recs and recs[-1]["direction"] == "plan" and recs[-1]["picked"] is True
        assert recs[-1]["ask"]["s"] == "A0" and recs[-1]["ask"]["v"] == "file"

    def test_a_direction_sent_without_picked_counts_as_picked(self, client):
        """The member sent the word -> picked True. Mutation: default False."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        r = _post(client, h, tid, {"content": TEXT, "direction": "action"})
        assert r.status_code == 200 and r.json()["picked"] is True

    def test_the_second_turn_carries_up_and_the_prior_ask(self, client, _isolate):
        """Turn 2's payload has UP (the prior seal against this read) and
        ask_prev = turn 1's recorded ask. Mutation: never read the seal's
        ask -> ask_prev None."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        assert _post(client, h, tid, {"content": TEXT}).status_code == 200
        first = json.loads(_isolate.calls[0][1].split("\n\n", 1)[1])
        assert first["UP"] is None and first["up_reason"] == "no prior seal"
        assert _post(client, h, tid, {"content": "The judge granted my motion, but the agency appealed."}).status_code == 200
        second = json.loads(_isolate.calls[3][1].split("\n\n", 1)[1])
        assert second["turn"] == 1 and second["UP"] is not None and second["up_reason"] is None
        assert set(second["UP"]["score"]) == {"matched", "missed", "undefined", "per"}
        assert second["ask_prev"] is not None and second["ask_prev"]["v"] == "file"

    def test_the_ledger_is_written_per_relationship(self, client):
        """relationships.ledger.{tid} and .seatmap.{tid} exist after a turn,
        with the two verb slots. Mutation: write only the seat map."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        assert _post(client, h, tid, {"content": TEXT}).status_code == 200
        led = memory_vault.vault_get(user, "relationships.ledger." + tid)
        sm = memory_vault.vault_get(user, "relationships.seatmap." + tid)
        assert led["turns"] == 1 and sm["by_key"].get("agency")
        agency = sm["by_key"]["agency"]
        assert "verb_self" in led["seats"][agency] and "verb_field" in led["seats"][agency]

    def test_diagnostic_routes_to_the_sovereign_pin_and_names_it_unprovisioned(self, client, _isolate):
        """direction=diagnostic -> every lane goes to local:llama3.1; the mock
        answer renders 'sovereign seat not provisioned', sovereign =
        not_provisioned, mock True. Mutation: route diagnostic to the thread
        model -> the fake returns rows and the reply is a reading."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        r = _post(client, h, tid, {"content": TEXT, "direction": "diagnostic", "picked": True})
        assert r.status_code == 200, r.text
        assert {m for m, _ in _isolate.calls} == {mr._ENGINE_HARD_PIN["local"]}
        body = r.json()
        assert body["sovereign"] == "not_provisioned" and body["mock"] is True
        assert body["assistant_message"]["content"].startswith("sovereign seat not provisioned")
        assert body["model_id"] == mr._ENGINE_HARD_PIN["local"]

    def test_a_halt_surfaces_as_the_reply_and_sends_nothing(self, client, _isolate, monkeypatch):
        """A leak the runner finds halts the workflow: zero vendor calls, the
        reply is the halt's rationale, reading.halted True, mock None. The
        poison rides the route's composed bundle (compose itself refuses a
        leak, so the runner is the exit under test). Mutation: send anyway
        -> three calls."""
        import intelligence_kernel as ik
        real_compose = ik.compose_thread_turn

        def poisoned(*a, **kw):
            composed = real_compose(*a, **kw)
            t = composed["payload"]["EP"]["triples"][0]
            t["o"], t["ok"] = "agency", "lex"              # a seat's NAME in a member slot
            return composed

        monkeypatch.setattr(ik, "compose_thread_turn", poisoned)
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        r = _post(client, h, tid, {"content": TEXT})
        assert r.status_code == 200, r.text
        assert _isolate.calls == []
        body = r.json()
        assert body["assistant_message"]["content"].startswith("halt: ")
        assert body["reading"]["halted"] is True and body["mock"] is None

    def test_a_halted_diagnostic_turn_reads_the_seat_undefined_not_provisioned(self, client, _isolate, monkeypatch):
        """No lane was sent, so the daemon's state is unread: sovereign is
        'undefined', never 'provisioned' (D5; the refuter's should).
        Mutation: derive provisioned from mock_all alone -> 'provisioned'."""
        import intelligence_kernel as ik
        real_compose = ik.compose_thread_turn

        def poisoned(*a, **kw):
            composed = real_compose(*a, **kw)
            t = composed["payload"]["EP"]["triples"][0]
            t["o"], t["ok"] = "agency", "lex"
            return composed

        monkeypatch.setattr(ik, "compose_thread_turn", poisoned)
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        r = _post(client, h, tid, {"content": TEXT, "direction": "diagnostic", "picked": True})
        assert r.status_code == 200, r.text
        assert _isolate.calls == []
        assert r.json()["sovereign"] == "undefined" and r.json()["reading"]["provisioned"] is None

    def test_the_reserve_is_taken_on_the_algebra_not_the_text(self, client, caplog):
        """The meter's est_in is computed over the three lane prompts, which
        is far more than the 84-char turn. Mutation: reserve on req.content
        -> est_in ~27."""
        import logging
        caplog.set_level(logging.INFO, logger="clarityos.compute_meter")
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        assert _post(client, h, tid, {"content": TEXT}).status_code == 200
        lines = [rec.getMessage() for rec in caplog.records if "meter reserve" in rec.getMessage()]
        assert lines, "no reserve line"
        est = int(re.search(r"est_in=(\d+)", lines[-1]).group(1))
        assert est > 3 * 300   # three lane frames alone exceed 900 chars ≈ 280 tokens; the payload rides on top
        # the output ceiling is counted once per lane (three calls, three
        # ceilings). Mutation: reserve one ceiling -> max_out=4096.
        assert "max_out=12288" in lines[-1]

    def test_a_changed_direction_does_not_halt_the_turn(self, client, _isolate):
        """R-366-B: picking ``action`` after a ``query`` turn is the member's
        own authorization, not drift -- both turns read, six lane calls,
        nothing halted. Mutation: gate the INTENT drift on the threshold ->
        the second turn halts with zero lanes."""
        user, h = _member()
        tid = threads_vault.create_thread(user, title="seat")["thread_id"]
        assert _post(client, h, tid, {"content": TEXT}).status_code == 200
        r = _post(client, h, tid, {"content": "The judge granted my motion.", "direction": "action", "picked": True})
        assert r.status_code == 200, r.text
        assert r.json()["reading"]["halted"] is False and r.json()["reading"]["lanes"] == ["time", "ambient", "role"]
        assert len(_isolate.calls) == 6
