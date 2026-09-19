"""
#366 A8 -- the reassembler: 0 rows -> undefined; the relation named; at most
three clauses, robust before contested, the asker's rows first; the ask
present iff the asker holds a seat, phrased as the row read back, recorded
on the seal in a shape the prose guard accepts; the halt and the
un-provisioned sovereign seat rendered as themselves, never as a reading.
Then the fixture's u2 through the whole machine (from the Library path only;
skipped when absent -- R-366-A).

Every test names the mutation that breaks it.
"""
from __future__ import annotations

import io
import json
import os
import re

import pytest

pytest.importorskip("spacy", reason="#366 A1: spaCy is the parser (requirements.txt)")

import clause_parser as cp  # noqa: E402
import ep_up_payload as ep  # noqa: E402
import ep_up_turn  # noqa: E402
import lane_intersect as li  # noqa: E402
import memory_vault  # noqa: E402
import reassembler as ra  # noqa: E402
import seat_ledger as sl  # noqa: E402
import turn_record  # noqa: E402

FIXTURE = os.path.join(
    os.path.expanduser("~"), "ClarityOS_Library", "Launch GalileOnline", "200_Operator_Notes",
    "FIXTURE_366_thread_2215259_user_turns_2026-09-19.md",
)


def _sm_and_triples(text: str, classes: set | None = None) -> tuple:
    sm = sl.SeatMap()
    ts = sl.attribute(cp.parse_clauses(text), sm, author_classes=classes or set())
    return sm, ts


SPLIT = {"time": {"state": "met", "direction": "s->o", "mass": 0.5},
         "ambient": {"state": "violated", "direction": "s->o", "mass": 0.5},
         "role": {"state": "met", "direction": "o->s", "mass": 0.5}}


def _vals(n: int, state="met", robust=True, mass=0.5, direction="s->o") -> dict:
    return {i: {"state": state if robust else "undefined", "direction": direction if robust else "undefined",
                "mass": mass, "robust": robust,
                **({} if robust else {"candidates": ["met", "violated"], "split": dict(SPLIT)})} for i in range(n)}


def _read(**kw) -> dict:
    kw.setdefault("up", None); kw.setdefault("n_lanes", 3); kw.setdefault("turn", 0)
    return ra.reassemble(**kw)


# ---------------------------------------------------------------------------
# 0 rows -> undefined; the relation
# ---------------------------------------------------------------------------
class TestUndefinedAndRelation:
    def test_zero_rows_read_undefined_with_no_ask(self):
        """No triple at all: the head says so; no clause, no ask, relation
        undefined. Mutation: render a default clause -> clauses non-empty."""
        out = _read(triples=[], values={}, seatmap=sl.SeatMap(), asker_seats={"A0"})
        assert out["text"].startswith("reading: undefined — 0 rows")
        assert out["clauses"] == [] and out["ask"] is None and out["relation"] == "undefined"

    def test_rows_without_a_value_read_undefined_not_a_default(self):
        """Triples exist, no lane read them: '0 of N rows carried a value'.
        Mutation: count an undefined row as met -> a clause appears."""
        sm, ts = _sm_and_triples("The agency dismissed the complainant.")
        out = _read(triples=ts, values={}, seatmap=sm, asker_seats=set())
        assert "0 of %d rows carried a value" % len(ts) in out["text"]
        assert out["rows_read"] == 0 and out["clauses"] == []

    def test_the_relation_names_the_two_seats_of_the_top_row(self):
        """agency ↔ complainant, from the top row that holds two seats.
        Mutation: name the first row regardless -> a one-seat row's
        undefined."""
        sm, ts = _sm_and_triples("The agency dismissed the complainant. The complainant appealed.")
        out = _read(triples=ts, values=_vals(len(ts)), seatmap=sm, asker_seats=set())
        assert out["relation"] == "agency ↔ complainant"
        assert out["text"].splitlines()[0].startswith("reading · relation: agency ↔ complainant · rows 2")

    def test_a_row_with_one_seat_names_the_other_side_undefined(self):
        """VA dismissed the complaints: a lexical object is no second seat ->
        'VA ↔ undefined'. Mutation: name the lexical word as the other
        side -> 'VA ↔ complaint'."""
        sm, ts = _sm_and_triples("VA dismissed the complaints.")
        assert ts[0]["s"] and ts[0]["ok"] == "lex"
        out = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats=set())
        assert out["relation"] == "VA ↔ undefined"


# ---------------------------------------------------------------------------
# the clauses
# ---------------------------------------------------------------------------
class TestClauses:
    def test_at_most_three_robust_before_contested_asker_first(self):
        """Ten valued rows -> three lines; the asker's robust row leads; a
        contested row reads 'contested:' with state undefined. Mutation:
        drop the cap -> 10 lines; or rank contested first."""
        text = " ".join(["The agency dismissed the complainant."] * 4 + ["I filed complaints."] + ["The judge granted the motion."] * 5)
        sm, ts = _sm_and_triples(text)
        vals = _vals(len(ts))
        vals[0] = {"state": "undefined", "direction": "undefined", "mass": 0.9, "robust": False, "candidates": ["met", "violated"]}
        out = _read(triples=ts, values=vals, seatmap=sm, asker_seats={sl.SEAT_AUTHOR})
        assert len(out["clauses"]) == 3
        assert out["clauses"][0]["text"].startswith("1. I – file – performed")
        assert all("robust 3/3" in c["text"] for c in out["clauses"])
        assert not any("contested:" in c["text"] for c in out["clauses"])
        assert out["contested"] == 1 and out["robust"] == len(ts) - 1

    @pytest.mark.parametrize("state, word", [("met", "performed"), ("violated", "not performed"), ("avoided", "not performed"), ("transferred", "transferred")])
    def test_the_state_reads_as_a_three_token_row(self, state, word):
        """met -> performed · violated/avoided -> not performed · transferred.
        Mutation: map violated to performed."""
        sm, ts = _sm_and_triples("The agency dismissed the complainant.")
        out = _read(triples=ts, values=_vals(1, state=state), seatmap=sm, asker_seats=set())
        assert out["clauses"][0]["text"].startswith("1. agency – dismiss – %s" % word)

    def test_a_contested_row_says_so_carries_no_state_and_shows_the_split(self):
        """R-366-F: the split is carried INTO the reading -- which lane said
        what, state and direction -- and the row's state is undefined.
        Mutation: print the majority state; or drop the split text and print
        the candidates alone -> 'contested: met/violated'."""
        sm, ts = _sm_and_triples("The agency dismissed the complainant.")
        out = _read(triples=ts, values=_vals(1, robust=False), seatmap=sm, asker_seats=set())
        line = out["clauses"][0]["text"]
        assert "– undefined" in line and "robust" not in line
        assert "contested: time:met/s->o ambient:violated/s->o role:met/o->s" in line

    def test_a_contested_asker_row_carries_the_split_on_the_ask(self):
        """The ask of a contested row names the split and stores it on the
        seal in id/enum form. Mutation: drop the split from build_ask."""
        sm, ts = _sm_and_triples("I withdrew the hearing request.")
        out = _read(triples=ts, values=_vals(1, robust=False), seatmap=sm, asker_seats={sl.SEAT_AUTHOR})
        assert out["ask"]["split"] == {k: {"state": v["state"], "direction": v["direction"]} for k, v in SPLIT.items()}
        assert "split: time:met/s->o ambient:violated/s->o role:met/o->s" in out["ask_text"]

    def test_the_sealed_ask_takes_the_wire_object_never_the_masked_word(self):
        """seal_fields stores the WIRE triple's o/v (masked form), so a word
        the mask replaced never reaches the seal or the next turn's ask_prev.
        Mutation: store the reassembler's o -> 'marisol vega letter' on the
        seal (the refuter's must)."""
        import ep_up_turn
        fake_turn = {
            "composed": {"direction": "query", "picked": False,
                         "payload": {"EP": {"triples": [{"o": "masked", "v": "read", "ok": "lex"}]}}},
            "reading": {"ask": {"row": 0, "s": "A0", "v": "read", "o": "marisol vega letter", "ok": "lex"}},
        }
        fields = ep_up_turn.seal_fields(fake_turn)
        assert fields["ask"]["o"] == "masked" and fields["ask"]["v"] == "read"
        assert fields["direction"] == "query" and fields["picked"] is False

    def test_the_shape_line_rides_only_when_the_cascade_produced_one(self):
        """v24 response_shape -> 'field: direction … · phase … · risk …'; absent
        -> no such line. Mutation: print defaults when absent."""
        sm, ts = _sm_and_triples("The agency dismissed the complainant.")
        with_shape = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats=set(),
                           shape={"direction": "stalled", "phase": "none", "risk": "low", "sections": ["constraint", "phase", "operator"]})
        assert "field: direction stalled · phase none · risk low · sections constraint/phase/operator" in with_shape["text"]
        without = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats=set())
        assert "field:" not in without["text"]


# ---------------------------------------------------------------------------
# the ask
# ---------------------------------------------------------------------------
class TestTheAsk:
    def test_the_ask_fires_iff_the_asker_holds_a_seat(self):
        """Personal (A0 in a row) -> one ask, the row read back; ambient (no
        asker seat) -> none. Mutation: always ask -> the ambient text ends
        with an ask."""
        sm, ts = _sm_and_triples("I filed complaints against the agency.")
        personal = _read(triples=ts, values=_vals(len(ts)), seatmap=sm, asker_seats={sl.SEAT_AUTHOR})
        assert personal["ask"] is not None and personal["ask_text"].startswith("ask: (I, file, ")
        assert personal["text"].rstrip().endswith("— ?")
        sm2, ts2 = _sm_and_triples("The agency dismissed the complainant.")
        ambient = _read(triples=ts2, values=_vals(len(ts2)), seatmap=sm2, asker_seats={sl.SEAT_AUTHOR})
        assert ambient["ask"] is None and "ask:" not in ambient["text"]

    def test_a_declared_class_makes_the_asker_hold_the_seat(self):
        """WALK §1: 'complainant' is the pilot's own seat class -- an
        ambient-looking text carries an ask on the complainant's row.
        Mutation: asker seats = {A0} only -> no ask."""
        sm, ts = _sm_and_triples("Agencies pressure a complainant into withdrawing the request.", classes={"complainant"})
        asker = sl.asker_seat_ids(sm, {"complainant"})
        out = _read(triples=ts, values=_vals(len(ts)), seatmap=sm, asker_seats=asker)
        assert out["asker_holds_seat"] is True and out["ask"] is not None
        assert "complainant" in out["ask_text"]

    def test_the_ask_is_one_row_with_conserved_direction_load_and_cell(self):
        """conserved from the modality, direction from the lanes, load =
        mass + numbers, cell = the unread cell. Mutation: drop the cell."""
        # the agency is an agent in the second sentence, so the dative in the
        # first rides as its seat (two passes); 7,514 is a value, not a name
        sm, ts = _sm_and_triples("I must pay the agency 7,514 dollars. The agency billed me.")
        vals = _vals(len(ts), state="violated", direction="o->s", mass=0.7)
        up = {"expectation": {"primitives.P1": 1, "pressure_score": 2}, "observation": {},
              "score": {"matched": 1, "missed": 1, "undefined": 0, "per": {"primitives.P1": "matched", "pressure_score": "missed", "agency": "undefined"}}}
        out = _read(triples=ts, values=vals, seatmap=sm, asker_seats={sl.SEAT_AUTHOR}, up=up)
        ask = out["ask"]
        assert ask["conserved"] == "obligation" and ask["s"] == sl.SEAT_AUTHOR and ask["v"] == "pay"
        assert ask["o"] == "dollar" and ask["ok"] == "lex"                      # a value is not a name
        assert ask["load"]["mass"] == 0.7 and "7,514" in ask["load"]["num"]
        assert ask["cell"] == {"status": "missed", "keys": ["pressure_score"]}   # the unclaimed bearing is not a cell
        assert "direction: agency→I" in out["ask_text"]
        assert "cell: missed: pressure_score" in out["ask_text"]

    def test_no_prior_seal_is_named_as_the_cell(self):
        """Turn 0: the cell is 'no prior seal', never met. Mutation: default
        to met."""
        sm, ts = _sm_and_triples("I filed complaints.")
        out = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats={sl.SEAT_AUTHOR}, up=None)
        assert out["ask"]["cell"] == {"status": "no_prior_seal", "keys": []}
        assert "cell: no prior seal" in out["ask_text"]

    def test_the_ask_is_recorded_on_the_seal_under_the_prose_guard(self, reset_stores):
        """direction · picked · ask land on THIS turn's seal; multiword lemmas
        become single tokens; a None ask omits the key. Mutation: store the
        rendered ask text -> the prose guard raises."""
        user, tid = "ask_user", "t_ask"
        read = turn_record.build_geometry_observation("I withdrew the hearing request.")
        key = turn_record.seal_expectation(user, tid, 0, turn_record.persistence_expectation(read))
        sm, ts = _sm_and_triples("I withdrew the hearing request.")
        out = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats={sl.SEAT_AUTHOR})
        written = turn_record.annotate_seal(user, key, {"direction": "query", "picked": False, "ask": out["ask"]})
        rec = memory_vault.vault_get(user, key)
        assert rec["direction"] == "query" and rec["picked"] is False
        assert rec["ask"]["s"] == sl.SEAT_AUTHOR and rec["ask"]["v"] == "withdraw"
        assert " " not in rec["ask"]["o"]                       # hearing_request, one token
        assert written["ask"] == rec["ask"]
        key2 = turn_record.seal_expectation(user, tid, 1, turn_record.persistence_expectation(read))
        turn_record.annotate_seal(user, key2, {"direction": "plan", "picked": True, "ask": None})
        rec2 = memory_vault.vault_get(user, key2)
        assert "ask" not in rec2 and rec2["direction"] == "plan"
        with pytest.raises(ValueError):
            turn_record.annotate_seal(user, key2, {"ask": {"text": "a sentence about a person " * 3}})


# ---------------------------------------------------------------------------
# halt · sovereign seat
# ---------------------------------------------------------------------------
class TestHaltAndSovereign:
    def test_a_halt_renders_its_rationale_and_nothing_else(self):
        """No clause, no ask, halted True. Mutation: render clauses anyway."""
        sm, ts = _sm_and_triples("I filed complaints.")
        out = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats={sl.SEAT_AUTHOR},
                    halt={"step": "t1:time", "constraint": "A4.no_names", "description": "1 seat-map token(s) in the payload; the lane was not sent"})
        assert out["text"].startswith("halt: 1 seat-map token(s)") and "not resumed" in out["text"]
        assert out["halted"] is True and out["clauses"] == [] and out["ask"] is None

    def test_an_unprovisioned_sovereign_seat_is_named_never_read(self):
        """A mock local answer renders 'sovereign seat not provisioned' -- no
        clause from a mock, no ask. Mutation: read the mock's rows."""
        sm, ts = _sm_and_triples("I filed complaints.")
        out = _read(triples=ts, values=_vals(1), seatmap=sm, asker_seats={sl.SEAT_AUTHOR}, provisioned=False)
        assert out["text"].startswith("sovereign seat not provisioned")
        assert out["clauses"] == [] and out["ask"] is None


# ---------------------------------------------------------------------------
# the fixture's u2 through the machine (Library path only; R-366-A)
# ---------------------------------------------------------------------------
PROPER_NOUNS = ["EEOC", "Commission", "West", "Rule 56", "29 CFR 1614.109", "Office of Federal Sector", "Supreme Court"]


def _fixture_turn(n: int) -> str:
    txt = io.open(FIXTURE, encoding="utf-8").read()
    m = re.search(r"^## u%d[^\n]*\n(.*?)(?=\n## u|\Z)" % n, txt, flags=re.S | re.M)
    return m.group(1).strip()


@pytest.mark.skipif(not os.path.isfile(FIXTURE), reason="FIXTURE_366 is read from the Library path only (R-366-A); absent here")
class TestFixtureU2:
    def _run(self, text: str, classes: set):
        composed = ep_up_turn.compose_turn(text=text, direction="query", picked=False, seatmap=sl.SeatMap(), author_classes=classes)
        prompts = []

        def fake(model_id, prompt):
            lane = prompt.split("lane=", 1)[1].split(" ", 1)[0]
            prompts.append(prompt)
            payload = json.loads(prompt.split("\n\n", 1)[1])
            rows = [{"i": i, "state": ("violated" if t["neg"] else "met"), "direction": "s->o" if t["ok"] == "seat" else "undefined", "mass": 0.3}
                    for i, t in enumerate(payload["EP"]["triples"])]
            return {"ok": True, "model_id": model_id, "provider": "fake", "text": json.dumps({"v": "lane.v1", "lane": lane, "rows": rows}), "mock": False, "ts": 0.0}

        lanes = ep_up_turn.run_lanes(composed=composed, model_id="openai:gpt-5.4", route_request_fn=fake, request_id="fixture", actor="pilot")
        inter, values = ep_up_turn.consolidate(composed, lanes)
        asker = sl.asker_seat_ids(composed["seatmap"], composed["classes"])
        reading = ra.reassemble(triples=composed["triples"], values=values, seatmap=composed["seatmap"], asker_seats=asker,
                                up=None, n_lanes=inter["n_lanes"], turn=1)
        return composed, prompts, reading

    def test_no_proper_noun_from_the_header_survives_into_any_lane_prompt(self):
        """The packet's A4 refuter over the real text: every listed proper noun
        absent from all three prompts as a whole word; name_leak empty; the
        chain in reading order. Mutation: skip the mask -> 'EEOC' or 'West'
        rides."""
        composed, prompts, _ = self._run(_fixture_turn(2), {"complainant"})
        assert len(prompts) == 3
        for p in prompts:
            for noun in PROPER_NOUNS:
                assert not re.search(r"(?<![A-Za-z0-9])" + re.escape(noun) + r"(?![A-Za-z0-9])", p), noun
        assert ep.name_leak(composed["payload"], composed["seatmap"].names(), composed["seatmap"].proper_tokens()) == set()
        assert ep.in_reading_order(composed["payload"]["EP"]["triples"]) is True
        assert composed["payload"]["EP"]["masked"] >= 0

    def test_the_pilots_seat_class_makes_u2_end_with_an_ask_and_names_the_relation(self):
        """u2 names no first person; the declared class 'complainant' (WALK §1)
        puts the asker in the text, so the example return ends with an ask
        and the relation names the complainant. Mutation: ignore classes ->
        no ask on u2."""
        composed, _, reading = self._run(_fixture_turn(2), {"complainant"})
        assert not any(t["s"] == sl.SEAT_AUTHOR for t in composed["triples"])
        assert reading["asker_holds_seat"] is True and reading["ask_text"] is not None
        assert "complainant" in reading["relation"]
        assert len(reading["clauses"]) == 3

    def test_without_the_class_u2_is_ambient_and_carries_no_ask(self):
        """The control: the same text, no declared class -> reading, no ask."""
        _, _, reading = self._run(_fixture_turn(2), set())
        assert reading["ask"] is None and reading["rows_read"] > 0
