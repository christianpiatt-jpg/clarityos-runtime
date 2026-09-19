"""
#366 A2 + A4 -- the seat ledger and the payload: seats on first appearance,
verb_self / verb_field never merged, signature keying, the pressure sign
named on the row, the author's classes, the vault round-trip, and the A4
refuter as a unit test over the composed payload.

Every test names the mutation that breaks it.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("spacy", reason="#366 A1: spaCy is the parser (requirements.txt)")

import clause_parser as cp  # noqa: E402
import ep_up_payload as ep  # noqa: E402
import memory_vault  # noqa: E402
import seat_ledger as sl  # noqa: E402
import turn_record  # noqa: E402


def triples_for(text: str, sm: sl.SeatMap | None = None, classes: set | None = None) -> tuple:
    sm = sm or sl.SeatMap()
    rows = cp.parse_clauses(text)
    return sl.attribute(rows, sm, author_classes=classes or set()), sm


# ---------------------------------------------------------------------------
# seats
# ---------------------------------------------------------------------------
class TestSeats:
    def test_first_person_is_A0_and_every_agent_holds_a_seat(self):
        """I -> A0; VA -> a seat; the judge -> a seat. Mutation: seat only
        entities -> the judge's row has s None."""
        ts, sm = triples_for("I filed complaints. VA dismissed them. The judge granted the motion.")
        s = [t["s"] for t in ts]
        assert s[0] == sl.SEAT_AUTHOR
        assert all(x for x in s), s
        assert sm.name_of(s[2]) == "judge"

    def test_ids_are_assigned_on_first_appearance_and_are_stable(self):
        """The same map across two turns keeps the agency's id. Mutation:
        renumber per call -> the second turn's agency is a new id."""
        sm = sl.SeatMap()
        t1, _ = triples_for("The agency dismissed the complaint.", sm)
        t2, _ = triples_for("The agency appealed.", sm)
        assert t1[0]["s"] == t2[0]["s"]
        assert sm.lookup("agency") == t1[0]["s"]

    def test_an_entity_is_an_org_seat_marked_proper(self):
        """EEOC -> org_1 with its token in proper_tokens. Mutation: seat ORG
        entities as plain seats -> the id prefix changes and the token is
        not proper."""
        ts, sm = triples_for("The EEOC denied the request.")
        assert ts[0]["s"].startswith("org_")
        assert "eeoc" in sm.proper_tokens()

    def test_a_citation_is_a_reference_never_the_author(self):
        """Article I / Part I -> ref ids; no A0 anywhere. Mutation: seat a
        reference as a party -> prefix S_."""
        ts, sm = triples_for("Article I was informed by Part I of Exhibit I.")
        t = ts[0]
        assert t["s"].startswith("ref_") and t["o"].startswith("ref_")
        assert sl.SEAT_AUTHOR not in {t["s"], t["o"]} | set(t["os"])

    def test_a_nominalization_is_N_with_its_link(self):
        """the agency's dismissal -> N_n with link = the agency's seat.
        Mutation: substitute the link for the agent -> s is the agency."""
        ts, sm = triples_for("The agency's dismissal of the complaint ended the case.")
        t = ts[0]
        assert t["s"].startswith("N_")
        assert t["link"] == sm.lookup("agency")

    def test_an_object_that_is_an_agent_anywhere_in_the_turn_is_seated(self):
        """Two passes: the complainant is an object in sentence 1 and an agent
        in sentence 2, so sentence 1's object rides as the id. Mutation: a
        single pass -> sentence 1's object is the lexical word."""
        ts, sm = triples_for("The judge dismissed the complainant. The complainant appealed.")
        assert ts[0]["ok"] == "seat" and ts[0]["o"] == ts[1]["s"]

    def test_an_object_never_seated_is_lexical(self):
        """records -> the head lemma, ok lex. Mutation: seat every object ->
        ok seat."""
        ts, _ = triples_for("VA shared records with the boss.")
        assert ts[0]["ok"] == "lex" and ts[0]["o"] == "record"

    def test_a_proper_noun_object_the_recogniser_missed_is_seated_not_worded(self):
        """'the Piatt letter' is a name whether or not NER spanned it: the
        object holds a seat whose tokens are proper, and the word never
        rides. Mutation: drop object_proper from _kind_for_object -> ok lex
        'Piatt letter' (the refuter's must)."""
        ts, sm = triples_for("The judge read the Piatt letter.")
        t = ts[0]
        assert t["ok"] == "seat" and t["o"] in sm.by_id
        assert "piatt" in sm.proper_tokens()

    def test_an_unresolved_pronoun_is_PRO_not_a_guess(self):
        """It -> PRO: no coreference is done. Mutation: seat pronouns as
        parties -> S_n named 'it'."""
        ts, _ = triples_for("It makes sense to allow the agency to develop evidence.")
        assert ts[0]["s"] == sl.SEAT_PRONOUN


# ---------------------------------------------------------------------------
# two verb slots, never merged; signature keying; the pressure sign
# ---------------------------------------------------------------------------
class TestTwoSlots:
    def test_verb_self_and_verb_field_are_two_dicts(self):
        """dismiss lands in the agency's verb_self and the complainant's
        verb_field, keyed by the other seat. Mutation: fold both into one
        dict -> the complainant's verb_self carries dismiss."""
        ts, sm = triples_for("The agency dismissed the complainant. The complainant appealed the dismissal.")
        ledger = sl.fold_slots({"seats": {}}, ts)
        agency, complainant = sm.lookup("agency"), sm.lookup("complainant")
        assert "dismiss|%s" % complainant in ledger["seats"][agency]["verb_self"]
        assert "dismiss|%s" % agency in ledger["seats"][complainant]["verb_field"]
        assert "dismiss|%s" % agency not in ledger["seats"][complainant]["verb_self"]
        assert ledger["seats"][agency]["verb_self"] is not ledger["seats"][agency]["verb_field"]

    def test_the_same_verb_under_two_objects_is_two_rows(self):
        """WALK §1: allow · the record / allow · the appeal are two signatures.
        Mutation: key by verb alone -> one signature with count 2."""
        ts, sm = triples_for("The agency allowed the record. The agency allowed the appeal.")
        ledger = sl.fold_slots({"seats": {}}, ts)
        self_slot = ledger["seats"][sm.lookup("agency")]["verb_self"]
        allows = [k for k in self_slot if k.startswith("allow|")]
        assert len(allows) == 2 and all(self_slot[k] == 1 for k in allows)

    def test_the_pressure_sign_is_named_with_its_basis(self):
        """sign(field - self), basis count_difference, on the row: the
        complainant is dismissed twice (field 2) and appeals once (self 1)
        -> +1; the agency dismisses once and is acted on by nobody -> -1.
        Mutation: drop the basis key, or compute self - field -> sign flips."""
        ts, sm = triples_for("The agency dismissed the complainant. The judge dismissed the complainant. The complainant appealed.")
        ledger = sl.fold_slots({"seats": {}}, ts)
        p = sl.pressure_sign(ledger, sm.lookup("complainant"))
        assert p == {"sign": 1, "field": 2, "self": 1, "basis": "count_difference"}
        q = sl.pressure_sign(ledger, sm.lookup("agency"))
        assert q == {"sign": -1, "field": 0, "self": 1, "basis": sl.PRESSURE_BASIS}

    def test_an_object_never_seated_takes_no_field_verb(self):
        """The two-pass rule's other side: a lexical object is a word, not a
        seat, so nothing is applied TO it. Mutation: fold lexical objects
        into verb_field under their word -> a 'complainant' key appears."""
        ts, sm = triples_for("The agency dismissed the complainant.")
        ledger = sl.fold_slots({"seats": {}}, ts)
        assert sm.lookup("complainant") is None
        assert set(ledger["seats"]) == {sm.lookup("agency")}


# ---------------------------------------------------------------------------
# ledger rows -- demand / resist frames, the state from the lanes
# ---------------------------------------------------------------------------
class TestLedgerRows:
    def test_the_frames_that_write(self):
        """obligation · negated expected · event with a contrast marker write;
        a plain event does not. Mutation: drop the contrast clause -> the
        third is False."""
        assert sl.is_demand_or_resist({"mod": "obligation"}) is True
        assert sl.is_demand_or_resist({"mod": "expected", "neg": True}) is True
        assert sl.is_demand_or_resist({"mod": "event", "con": ["but"]}) is True
        assert sl.is_demand_or_resist({"mod": "event", "con": []}) is False
        assert sl.is_demand_or_resist({"mod": "expected", "neg": False}) is False

    def test_the_state_comes_from_the_consolidated_read_else_undefined(self):
        """A robust state rides; a contested or missing one is undefined
        (D5). Mutation: default the state to met -> the second row reads
        met."""
        ts, sm = triples_for("Agencies must invest resources. Complainants must respond.")
        assert len(ts) == 2
        rows = sl.ledger_rows(ts, {0: {"state": "violated", "direction": "s->o", "mass": 0.5}}, turn=3, ledger={"seats": {}})
        assert [r["state"] for r in rows] == ["violated", "undefined"]
        assert all(r["since_turn"] == 3 and r["frame"] == "obligation" for r in rows)
        assert rows[0]["pressure"]["basis"] == "count_difference"

    def test_a_state_outside_the_vocabulary_is_undefined(self):
        """``met-ish`` is not a state. Mutation: pass the string through."""
        ts, _ = triples_for("Agencies must invest resources.")
        rows = sl.ledger_rows(ts, {0: {"state": "met-ish"}}, turn=0, ledger={"seats": {}})
        assert rows[0]["state"] == "undefined"


# ---------------------------------------------------------------------------
# the author's classes and the asker's seats
# ---------------------------------------------------------------------------
class TestAuthorClasses:
    def test_learned_from_the_authors_own_copula(self):
        """``I am a complainant`` -> {complainant}; an adjective complement is
        not a class; a NEGATED copula declares nothing. Mutation: learn from
        any copula -> the agency's class leaks in; ignore negation -> lawyer."""
        assert sl.learn_author_classes(cp.parse_clauses("I am a complainant.")) == {"complainant"}
        assert sl.learn_author_classes(cp.parse_clauses("I am tired.")) == set()
        assert sl.learn_author_classes(cp.parse_clauses("The agency is a respondent.")) == set()
        assert sl.learn_author_classes(cp.parse_clauses("I am not a lawyer.")) == set()

    def test_a_reporter_pronoun_is_PRO_not_a_party(self):
        """'He said the agency must respond' -- the reporter is the unresolved
        pronoun seat, never a party named 'he'. Mutation: seat the prov key
        -> S_n 'he' in the map."""
        ts, sm = triples_for("He said the agency must respond.")
        respond = [t for t in ts if t["v"] == "respond"][0]
        assert respond["prov"] == sl.SEAT_PRONOUN
        assert "he" not in {v["name"].lower() for v in sm.by_id.values()}

    def test_asker_seats_are_A0_plus_the_class_seats(self):
        """A seat named for a declared class counts as the asker's. Mutation:
        return {A0} only -> the complainant row is not the asker's."""
        ts, sm = triples_for("Complainants can use the costs of discovery.")
        ids = sl.asker_seat_ids(sm, {"complainant"})
        assert sl.SEAT_AUTHOR in ids and sm.lookup("complainant") in ids
        assert sl.asker_seat_ids(sm, set()) == {sl.SEAT_AUTHOR}
        assert ts[0]["asker"] is False  # no class was passed to attribute
        ts2, sm2 = triples_for("Complainants can use the costs of discovery.", classes={"complainant"})
        assert ts2[0]["asker"] is True


# ---------------------------------------------------------------------------
# persistence -- the vault namespace and the round-trip
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_the_namespace_is_allowed_and_both_halves_round_trip(self, reset_stores):
        """apply_turn writes relationships.ledger.{tid} and .seatmap.{tid};
        load returns the same ids. Mutation: drop the namespace from
        ALLOWED_NAMESPACES -> vault_put raises."""
        assert sl.NAMESPACE in memory_vault.ALLOWED_NAMESPACES
        user, tid = "ledger_user", "t366"
        ts, sm = triples_for("The agency dismissed the complainant. Complainants must respond.")
        out = sl.apply_turn(user, tid, ts, {1: {"state": "avoided", "direction": "s->o", "mass": 0.4}}, 0, sm, learned_classes={"complainant"})
        assert out["rows"] and out["rows"][0]["state"] == "avoided"
        ledger, sm2 = sl.load(user, tid)
        assert sm2.lookup("agency") == sm.lookup("agency")
        assert ledger["turns"] == 1 and ledger["author_classes"] == ["complainant"]
        assert set(memory_vault.vault_list_prefix(user, "relationships.").keys()) == {
            "relationships.ledger.%s" % tid, "relationships.seatmap.%s" % tid,
        }

    def test_declare_author_class_persists(self, reset_stores):
        """WALK §1's declaration survives a reload. Mutation: write to the
        map and not the ledger -> load reads []."""
        sl.declare_author_class("u", "t", "Complainant")
        ledger, _ = sl.load("u", "t")
        assert ledger["author_classes"] == ["complainant"]


# ---------------------------------------------------------------------------
# A4 -- the payload and the refuter
# ---------------------------------------------------------------------------
def _compose(text: str, sm: sl.SeatMap | None = None, **kw) -> tuple:
    sm = sm or sl.SeatMap()
    rows = cp.parse_clauses(text)
    ts = sl.attribute(rows, sm, author_classes=set())
    read = turn_record.build_geometry_observation(text)
    p = ep.compose(direction=kw.get("direction", "query"), picked=kw.get("picked", False), turn=kw.get("turn", 0),
                   triples=ts, verb_owner_set={"D": 3, "T": 0.1, "N": 0.2, "counts": {"hydronic": {"flows": 1}}},
                   up=kw.get("up"), ask_prev=kw.get("ask_prev"),
                   seatmap_names=sm.names(), proper_tokens=sm.proper_tokens())
    return p, ts, sm


class TestPayload:
    def test_the_shape_and_the_direction_bit(self):
        """v · direction · picked · turn · EP{triples, hydronic, D, T, N} ·
        UP None with up_reason on turn 0. Mutation: drop up_reason -> a bare
        None with no reason."""
        p, ts, sm = _compose("I filed complaints.", direction="action", picked=True)
        assert p["v"] == ep.PAYLOAD_VERSION and p["direction"] == "action" and p["picked"] is True
        assert p["UP"] is None and p["up_reason"] == "no prior seal"
        assert p["EP"]["D"] == 3 and p["EP"]["T"] == 0.1 and p["EP"]["hydronic"]["direction"] == "undefined"
        assert p["EP"]["hydronic"]["counts"] == {"flows": 1}
        assert p["EP"]["triples"][0]["s"] == sl.SEAT_AUTHOR and p["EP"]["triples"][0]["v"] == "file"

    def test_a_direction_outside_the_four_words_is_refused(self):
        """Mutation: default an unknown word to query -> no ValueError."""
        with pytest.raises(ValueError):
            ep.validate_direction("hunch", True)

    def test_triples_ride_in_reading_order(self):
        """The reading-order refuter over the payload's chain. Mutation:
        emit triples sorted by seat id -> False."""
        p, _, _ = _compose("The agency appealed. I filed complaints, but the judge dismissed them.")
        assert ep.in_reading_order(p["EP"]["triples"]) is True
        assert ep.in_reading_order(list(reversed(p["EP"]["triples"]))) is False

    def test_up_carries_expectation_observation_and_the_score(self):
        """UP from a prior seal record and this read: the R15 tally rides.
        Mutation: score against the observation's own keys -> matched == all."""
        read1 = turn_record.build_geometry_observation("I filed complaints against the agency.")
        prior = {"turn_index": 2, "expectation": turn_record.persistence_expectation(read1)}
        read2 = turn_record.build_geometry_observation("The agency must respond or the judge will rule.")
        up = ep.compose_up(prior, read2)
        assert up["prior_turn"] == 2
        assert "source" not in up["expectation"]
        assert set(up["score"]) == {"matched", "missed", "undefined", "per"}
        assert up["score"]["matched"] + up["score"]["missed"] + up["score"]["undefined"] == len(up["score"]["per"])
        assert ep.compose_up(None, read2) is None


class TestA4Refuter:
    def test_a_lexical_object_that_names_a_seat_is_masked(self):
        """A hand-built payload with o == a seat's name: name_leak finds it;
        compose's mask loop removes it. Mutation: skip _mask in compose ->
        RuntimeError (the loop is the proof, not the promise)."""
        sm = sl.SeatMap()
        sm.seat_for("hearing request", "seat", mention="the hearing request")
        payload = {"EP": {"triples": [{"s": "S_9", "v": "withdraw", "o": "hearing request", "ok": "lex", "con": []}]}}
        assert ep.name_leak(payload, sm.names(), sm.proper_tokens()) == {"hearing request"}
        masked = ep._mask(payload, sm.names(), sm.proper_tokens())
        assert masked == 1 and payload["EP"]["triples"][0]["o"] == ep.MASKED
        assert ep.name_leak(payload, sm.names(), sm.proper_tokens()) == set()

    def test_a_proper_token_leaks_from_any_member_slot(self):
        """EEOC in a verb slot or a contrast slot is a leak (the fixture's
        list is token-level). Mutation: check whole names only -> a token
        inside a longer string passes."""
        sm = sl.SeatMap()
        sid = sm.seat_for("EEOC", "org", mention="the EEOC")
        payload = {"EP": {"triples": [{"s": sid, "v": "eeoc", "o": "request", "ok": "lex", "con": ["per EEOC"]}]}}
        leak = ep.name_leak(payload, sm.names(), sm.proper_tokens())
        assert "eeoc" in leak and "per eeoc" in leak

    def test_ids_keys_and_enums_never_read_as_a_leak(self):
        """A seat named ``state`` or ``direction`` must not make the payload's
        own vocabulary trip the refuter. Mutation: scan the serialized JSON
        for whole names -> the keys leak."""
        sm = sl.SeatMap()
        sm.seat_for("state", "seat", mention="the state")
        sm.seat_for("direction", "seat", mention="the direction")
        p, _, _ = _compose("The state regulates the market.", sm)
        assert ep.name_leak(p, sm.names(), sm.proper_tokens()) == set()
        assert json.dumps(p).count("direction") >= 1  # the key is there; it is not a leak

    def test_a_verb_that_matches_a_common_seat_name_is_not_masked(self):
        """A clause-subject seat named ``allow`` does not mask the verb allow
        in another row (a verb is not an identity); a PROPER token still
        does. Mutation: check verbs against every name -> the verb masks."""
        sm = sl.SeatMap()
        sm.seat_for("allow", "nominal", mention="allowing")
        payload = {"EP": {"triples": [{"s": "S_1", "v": "allow", "o": "record", "ok": "lex", "con": []}]}}
        assert ep._mask(payload, sm.names(), sm.proper_tokens()) == 0
        assert payload["EP"]["triples"][0]["v"] == "allow"
        sm.seat_for("West", "ref", mention="West, supra")
        payload2 = {"EP": {"triples": [{"s": "S_1", "v": "west", "o": "record", "ok": "lex", "con": []}]}}
        assert ep._mask(payload2, sm.names(), sm.proper_tokens()) == 1

    def test_compose_returns_clean_by_construction(self):
        """Over a text with a REAL collision -- 'Rule 56' is a reference whose
        proper tokens include 'rule', and the next sentence's VERB is 'rule'
        -- compose masks the colliding verb slot and its output passes
        name_leak. Mutation: return before the mask loop -> the RuntimeError
        guard fires on this very text (the refuter caught the first version
        of this test naming a mutation its text could not trip; the second
        version's collision was removed by seating proper-noun objects)."""
        p, ts, sm = _compose("The judge applied Rule 56 to the motion. The judge will rule on the motion.")
        assert "rule" in sm.proper_tokens()
        assert p["EP"]["masked"] >= 1
        assert any(t["v"] == ep.MASKED for t in p["EP"]["triples"])
        assert ep.name_leak(p, sm.names(), sm.proper_tokens()) == set()

    def test_the_proper_flag_survives_the_vault_round_trip(self):
        """A PERSON seat marked proper on turn N keeps token-level protection
        on turn N+1. Mutation: drop 'proper' in SeatMap.__init__ -> the
        reloaded map's proper_tokens is empty (the refuter's must)."""
        sm = sl.SeatMap()
        sid = sm.seat_for("Marisol Vega", "seat", mention="Marisol Vega")
        sm.mark_proper(sid)
        assert sorted(sm.proper_tokens()) == ["marisol", "vega"]
        assert sl.SeatMap(sm.to_dict()).proper_tokens() == sm.proper_tokens()

    def test_an_underscored_compound_still_leaks(self):
        """The seal spells a compound with underscores; the refuter reads
        both spellings. Mutation: drop the underscore normalisation in
        _leaks -> 'marisol_vega_letter' passes."""
        assert ep._leaks("marisol_vega_letter", {"marisol vega"}, set()) is True
        assert ep._leaks("marisol vega letter", {"marisol vega"}, set()) is True
        assert ep._leaks("hearing_request", {"marisol vega"}, set()) is False

    def test_a_references_numbers_are_its_name_not_the_load(self):
        """'Rule 56' rides as ref_n with NO num; a number that is a proper token
        in a lexical slot is masked. Mutation: copy the parser's numbers for a
        seated object -> num ['56'] beside ref_1."""
        p, ts, sm = _compose("The judge applied Rule 56 to the motion.")
        refs = [t for t in p["EP"]["triples"] if t["ok"] == "seat" and str(t["o"]).startswith("ref_")]
        assert refs and all(t["num"] == [] for t in refs)
        assert "56" in sm.proper_tokens()
        poisoned = {"EP": {"triples": [{"s": "S_1", "v": "cite", "o": "page", "ok": "lex", "con": [], "num": ["56"]}]}}
        assert ep._mask(poisoned, sm.names(), sm.proper_tokens()) == 1
        assert poisoned["EP"]["triples"][0]["num"] == [ep.MASKED]

    def test_identifier_numbers_never_ride(self):
        """A docket number or an SSN identifies; an amount is the load.
        Mutation: drop the identifier rule from _slot_leaks -> the docket
        rides in a lexical slot."""
        p, ts, sm = _compose("My case number is 0120182345 and I paid 7,514 dollars to the agency.")
        blob = ep.serialize(p)
        assert "0120182345" not in blob
        assert "7,514" in blob
        assert ep._identifier_number("0120182345") and ep._identifier_number("123-45-6789")
        assert not ep._identifier_number("7,514") and not ep._identifier_number("2026")
