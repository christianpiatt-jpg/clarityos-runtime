"""
#366 A1 -- the clause parser: the tuple on the recorded fragments, the
enumerator, the R-366-E modalities, negation, the contrast markers, the
nominalization, tense, the reading order.

Every test names the mutation that breaks it (the #374 discipline: eight
tautologies shipped in one build before it). The sentences are the WALK §1
own-clause list, the packet's two required rows, and shapes lifted from the
fixture's u1/u2 -- typed here as fragments, never the fixture's text.
"""
from __future__ import annotations

import pytest

spacy = pytest.importorskip("spacy", reason="#366 A1: spaCy is the parser (requirements.txt)")

import clause_parser as cp  # noqa: E402


def rows(text: str) -> list:
    return cp.parse_clauses(text)


def one(text: str, verb: str) -> cp.Clause:
    found = [r for r in rows(text) if r.verb_lemma == verb]
    assert found, "no row for verb %r in %r: %s" % (verb, text, [r.verb_lemma for r in rows(text)])
    return found[0]


# ---------------------------------------------------------------------------
# the tuple
# ---------------------------------------------------------------------------
class TestTheTuple:
    def test_i_filed_complaints_is_the_packets_first_row(self):
        """(I, file, complaints, neg=False, event, [], past, 0) with I as
        ``nsubj`` and complaints as ``dobj``. Mutation: read the object from
        the first noun instead of the dobj dependent -> object_dep changes."""
        r = one("I filed complaints.", "file")
        assert r.tuple8 == ("I", "file", "complaints", False, "event", [], "past", 0)
        assert r.agent_dep == "nsubj" and r.object_dep == "dobj"
        assert r.agent_first_person is True
        assert r.agent_key == "I" and r.object_key == "complaint"

    def test_a_row_carries_the_verb_position_for_the_reading_order(self):
        """verb_idx is the token index of the clause verb. Mutation: stamp
        the sentence index into verb_idx -> two rows in one sentence tie."""
        rs = rows("The judge granted the motion, but the agency appealed.")
        assert [r.verb_lemma for r in rs] == ["grant", "appeal"]
        assert rs[0].verb_idx < rs[1].verb_idx

    def test_empty_and_blank_text_parse_to_nothing(self):
        """No clause, no row -- never a placeholder row. Mutation: return a
        single undefined row for empty text -> len 1."""
        assert cp.parse_clauses("") == []
        assert cp.parse_clauses("   \n ") == []
        assert cp.parse_clauses(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# negation -- a neg dependent the tree carries (G7's blind spot, #369)
# ---------------------------------------------------------------------------
class TestNegation:
    def test_dont_want_to_go(self):
        """(I, want, go, neg=True, event, present). Mutation: drop the
        ``neg`` scan in _negated -> False."""
        r = one("I don't want to go.", "want")
        assert r.negation is True
        assert r.object_dep == "xcomp" and r.object_span == "go"
        assert r.tense == "present"
        assert r.modality == "event"

    def test_never_is_a_negation(self):
        """``never`` is a ``neg`` dependent. Mutation: only ``n't`` counts."""
        assert one("The EEOC has never defined the right.", "define").negation is True

    def test_no_on_the_object_is_a_negation(self):
        """A determiner *no* on the object negates the clause. Mutation:
        skip the object's det scan -> False."""
        assert one("The agency had no statement of facts.", "have").negation is True

    def test_the_control_is_false(self):
        """The refuter's other direction: an unnegated clause reads False."""
        assert one("VA dismissed the complaints.", "dismiss").negation is False


# ---------------------------------------------------------------------------
# the enumerator -- R-374-A closes in the tree, with the three guards
# ---------------------------------------------------------------------------
class TestTheEnumerator:
    def test_article_I_is_a_reference_not_the_author(self):
        """en_core_web_sm reads the *I* of "Article I" as nsubjpass (measured
        2026-09-19). Three guards make it a reference: the LAW entity, the
        citation span, the carrier noun before it. Mutation: drop all three
        (return True on the pronoun set alone) -> a first-person row."""
        rs = rows("Article I was informed by Part I of Exhibit I.")
        assert rs, "no rows"
        assert not any(r.agent_first_person or r.object_first_person for r in rs)
        r = one("Article I was informed by Part I of Exhibit I.", "inform")
        assert r.passive is True
        assert r.agent_key == "Part I" and r.agent_is_ref is True
        assert r.object_key == "Article I" and r.object_is_ref is True
        assert not any(k["first_person"] for k in r.inner_keys)

    @pytest.mark.parametrize("text, verb", [
        ("Title I applies to every agency.", "apply"),
        ("Schedule I lists the fees.", "list"),
        ("Phase I began in March.", "begin"),
    ])
    def test_title_schedule_phase_I_are_references(self, text, verb):
        """The carrier-noun guard alone (no LAW entity is guaranteed on these).
        Mutation: remove ``title``/``schedule``/``phase`` from the carriers."""
        r = one(text, verb)
        assert r.agent_first_person is False
        assert r.agent_is_ref is True

    def test_the_plain_pronoun_is_still_the_author(self):
        """The guard is three conditions, not a ban on *I*. Mutation: treat
        every *I* as a reference -> the WALK's own clauses lose their seat."""
        assert one("I applied for the hearing.", "apply").agent_first_person is True
        assert one("I am waiting for the judge.", "wait").agent_first_person is True

    @pytest.mark.parametrize("text, verb", [
        ("At this stage I want to withdraw the request.", "want"),
        ("For the most part I agreed with the judge.", "agree"),
        ("After reading the article I filed a complaint.", "file"),
        ("Yesterday I filed the complaint.", "file"),
    ])
    def test_a_lowercase_or_determined_carrier_does_not_swallow_the_author(self, text, verb):
        """The gate on condition (c): a carrier that is lowercase, or carries
        its own determiner, or is a time word, does not enumerate the I after
        it. Mutation: drop the capitalization/determiner gate -> 'stage I'
        and 'part I' seat the author as a third party named I (the refuter's
        must)."""
        assert one(text, verb).agent_first_person is True

    @pytest.mark.parametrize("text, verb", [
        ("Count I alleges retaliation.", "allege"),
        ("Table I lists the fees.", "list"),
        ("Paragraph I states the rule.", "state"),
    ])
    def test_the_complaints_own_enumerators_are_references(self, text, verb):
        """Count · Table · Paragraph are enumerator heads (a lexicon, named as
        one). Mutation: drop them from _ENUMERATOR_CARRIERS -> the author
        alleges retaliation."""
        r = one(text, verb)
        assert r.agent_first_person is False and r.agent_is_ref is True


# ---------------------------------------------------------------------------
# modality -- R-366-E
# ---------------------------------------------------------------------------
class TestModality:
    def test_would_is_counterfactual(self):
        """``would`` with no if-mark -> counterfactual. Mutation: map would
        to conditional unconditionally."""
        assert one("The agency would remain responsible for the record.", "remain").modality == "counterfactual"

    def test_would_under_an_if_mark_is_conditional(self):
        """The if-mark on the governing or governed clause turns would into
        conditional. Mutation: ignore the mark -> counterfactual."""
        text = "If the agency were notified, it would remain responsible."
        assert one(text, "remain").modality == "conditional"
        assert one(text, "notify").modality == "conditional"

    @pytest.mark.parametrize("text, verb", [
        ("The Commission could adopt the recommendation.", "adopt"),
        ("The judge might dismiss the request.", "dismiss"),
        ("The agency may petition the Commission.", "petition"),
        ("Complainants can use the costs of discovery.", "use"),
    ])
    def test_could_might_may_can_are_conditional(self, text, verb):
        """could / might / may -> conditional (R-366-E); ``can`` joins them
        as the present form, named in the return. Mutation: drop one modal
        from the set -> event."""
        assert one(text, verb).modality == "conditional"

    @pytest.mark.parametrize("text, verb", [
        ("Agencies must invest substantial resources.", "invest"),
        ("The judge should rule on the motion.", "rule"),
        ("Complainants need to respond to each assertion.", "respond"),
        ("Agencies have to litigate the full docket.", "litigate"),
        ("The agency shall respond to the complaint.", "respond"),
    ])
    def test_should_must_need_to_have_to_are_obligation(self, text, verb):
        """R-366-E's obligation set, including the two periphrastic forms
        through the xcomp, plus ``shall`` (legal drafting's obligation modal
        -- an extension named in the return). Mutation: drop the need/have
        xcomp rule; drop shall from the set."""
        assert one(text, verb).modality == "obligation"

    def test_identifier_numbers_are_not_the_load(self):
        """A docket number INSIDE the object phrase ('case number 0120182345'
        -- nummod of the object head, measured) never enters ``numbers``; an
        amount does. Mutation: drop is_identifier_number from _numbers -> the
        docket rides. (The first version put the number in a prepositional
        phrase outside the object span, where no rule was needed to exclude
        it -- the harness caught the vacuous assertion.)"""
        assert cp.is_identifier_number("0120182345") is True
        assert cp.is_identifier_number("123-45-6789") is True
        assert cp.is_identifier_number("7,514") is False and cp.is_identifier_number("2026") is False
        r = one("I filed case number 0120182345 against the agency.", "file")
        assert "0120182345" in r.object_span                   # it IS in the span the numbers are read from
        assert r.numbers == []                                  # ...and is not carried as the load
        assert r.object_key == "case number"                    # the key never holds it either
        r2 = one("I paid the agency 7,514 dollars.", "pay")
        assert r2.numbers == ["7,514"]

    @pytest.mark.parametrize("text, verb", [
        ("Approved agencies will impose liability.", "impose"),
        ("The agency is expected to issue a decision.", "issue"),
        ("The Commission likely refers the matter.", "refer"),
    ])
    def test_will_expected_to_likely_are_expected(self, text, verb):
        """R-366-E's expected set. Mutation: drop ``likely`` from the adverb
        set -> event on the third."""
        assert one(text, verb).modality == "expected"

    def test_a_speech_frame_reports_with_provenance(self):
        """``As X observed, Y`` -> Y is reported with prov = X; ``He said
        Z`` -> Z reported with prov = he. Mutation: return reported without
        the reporter's key -> prov None."""
        r = one("As the Supreme Court observed in West, the process is intended to be quicker.", "intend")
        assert r.modality == "reported" and r.prov_key == "Supreme Court"
        r2 = one("He said the agency had no statement of facts.", "have")
        assert r2.modality == "reported" and r2.prov_key == "he" and r2.negation is True

    def test_a_modal_under_a_reporter_keeps_the_modal_and_the_reporter(self):
        """Two fields, no information dropped: the clause's own modality wins
        the slot and ``prov`` still names the reporter. Mutation: let
        reported override -> modality reported, or drop prov -> None."""
        r = one("He said the agency must respond.", "respond")
        assert r.modality == "obligation" and r.prov_key == "he"

    def test_event_is_the_default_only_when_nothing_else_is_present(self):
        """The control: a dated act with no modal, no mark, no reporter."""
        assert one("VA dismissed the complaints.", "dismiss").modality == "event"

    @pytest.mark.parametrize("text, verb", [
        ("The agency would still be responsible.", "be"),
        ("The Commission could refer the complaint.", "refer"),
        ("If a hearing is necessary, the Commission refers the matter.", "refer"),
        ("The agency is expected to issue a decision.", "issue"),
    ])
    def test_the_packets_refuter_would_could_if_expected_to_are_never_event(self, text, verb):
        """The packet's A1 refuter, verbatim: would / could / if / expected to
        emitted as event -> FAIL."""
        assert one(text, verb).modality != "event"


# ---------------------------------------------------------------------------
# the contrast markers -- carried verbatim, never dropped (#380)
# ---------------------------------------------------------------------------
class TestContrast:
    @pytest.mark.parametrize("marker, text", [
        ("unlikely", "A hearing is unlikely to help."),
        ("suddenly", "The agency suddenly withdrew the motion."),
        ("reluctantly", "The judge reluctantly granted the motion."),
        ("only", "The rule applies only to agencies."),
        ("still", "The agency would still be responsible."),
        ("though", "The agency appealed, though the record was thin."),
        ("but", "The judge granted the motion, but the agency appealed."),
        ("even", "The agency appealed even where the record was thin."),
    ])
    def test_each_of_the_packets_eight_is_carried(self, marker, text):
        """The packet's eight markers each land in some row's contrast_span.
        Mutation: remove one from CONTRAST_MARKERS_PACKET -> that row empty."""
        carried = {m for r in rows(text) for m in r.contrast_span}
        assert marker in carried, (marker, [(r.verb_lemma, r.contrast_span) for r in rows(text)])

    def test_but_belongs_to_the_clause_it_introduces(self):
        """A coordinating marker rides the conj clause, not the clause before
        it. Mutation: assign cc markers to the head's own clause."""
        rs = rows("The judge reluctantly granted the motion, but the agency appealed.")
        by_verb = {r.verb_lemma: r.contrast_span for r in rs}
        assert "but" in by_verb["appeal"] and "but" not in by_verb["grant"]
        assert by_verb["grant"] == ["reluctantly"]

    def test_the_specimens_markers_ride_too(self):
        """rather than · than · if · however (the specimens' set). Mutation:
        drop the multiword scan -> ``rather than`` lost."""
        carried = {m for r in rows("Complainants need proper advice rather than a chatbot, however useful it is.") for m in r.contrast_span}
        assert "rather than" in carried
        assert "however" in carried

    def test_no_marker_means_an_empty_span(self):
        """The control: a plain sentence carries []."""
        assert all(r.contrast_span == [] for r in rows("VA dismissed the complaints."))


# ---------------------------------------------------------------------------
# the nominalization -- the agent row IS the nominalization; the seat is linked
# ---------------------------------------------------------------------------
class TestNominalization:
    def test_the_sharing_is_the_agent_and_the_author_is_inside_the_object(self):
        """(the sharing, cost, my job) -- agent_nominalization True, the
        first person rides the dative/poss inner keys, never the agent slot.
        Mutation: substitute the linked seat for the nominalization -> the
        agent flag is False."""
        r = one("The sharing of records cost me my job.", "cost")
        assert r.agent_nominalization is True and r.agent_key == "sharing"
        assert r.agent_first_person is False
        assert r.object_key == "job"
        assert any(k["first_person"] and k["dep"] == "dative" for k in r.inner_keys)

    def test_a_possessive_names_the_link(self):
        """``the agency's dismissal`` -> link key agency. Mutation: skip the
        poss scan -> None."""
        r = one("The agency's dismissal of the complaint ended the case.", "end")
        assert r.agent_nominalization is True
        assert r.agent_link_key == "agency"

    def test_a_gerund_subject_is_a_nominalization(self):
        """``Granting the request would be discretionary`` -- lemma grant,
        token -ing. Mutation: test the lemma's suffix instead of the token's
        -> False."""
        r = one("Granting the request would be discretionary.", "be")
        assert r.agent_nominalization is True

    def test_a_role_noun_is_not_a_nominalization(self):
        """``Commission`` ends in -sion and is a party. Mutation: drop the
        role-noun allowlist -> True."""
        assert one("The Commission decided the appeal.", "decide").agent_nominalization is False


# ---------------------------------------------------------------------------
# tense and the passive
# ---------------------------------------------------------------------------
class TestTenseAndPassive:
    @pytest.mark.parametrize("text, verb, tense", [
        ("I filed complaints.", "file", "past"),
        ("I am waiting for the judge.", "wait", "present"),
        ("The EEOC has never defined the right.", "define", "present"),
        ("Approved agencies will impose liability.", "impose", "future"),
        ("The agency asked the judge to develop the record.", "develop", "undefined"),
    ])
    def test_tense_from_the_finite_element_else_undefined(self, text, verb, tense):
        """The finite verb's morph, else the tensed auxiliary's, will ->
        future, a bare infinitive -> undefined (never guessed). Mutation:
        default undefined to present -> the infinitive reads present."""
        assert one(text, verb).tense == tense

    def test_a_passive_moves_the_subject_to_the_object_slot(self):
        """(agency, dismiss, complaint) from "The complaint was dismissed by
        the agency" -- agent from the by-phrase, object the passive subject.
        Mutation: keep nsubjpass as the agent -> the complaint dismisses."""
        r = one("The complaint was dismissed by the agency.", "dismiss")
        assert r.passive is True
        assert r.agent_key == "agency" and r.agent_dep == "agent"
        assert r.object_key == "complaint" and r.object_dep == "passive_subject"

    def test_a_passive_without_a_by_phrase_has_an_undefined_agent(self):
        """No agent is named -> undefined, never the patient promoted."""
        r = one("The complaint was dismissed.", "dismiss")
        assert r.agent_span == cp.UNDEFINED and r.object_key == "complaint"

    def test_a_passive_subject_inherited_through_a_conjunct_stays_the_patient(self):
        """'was filed by the member and dismissed by the agency': the second
        verb's agent is ITS by-phrase and the complaint stays in the object
        slot; 'was reviewed and denied' has an undefined agent. Mutation:
        take the inherited nsubjpass as the agent -> the complaint dismisses
        (the refuter's must)."""
        r = one("The complaint was filed by the member and dismissed by the agency.", "dismiss")
        assert r.passive is True
        assert r.agent_key == "agency" and r.agent_dep == "agent"
        assert r.object_key == "complaint" and r.object_dep == "passive_subject"
        r2 = one("The request was reviewed and denied.", "deny")
        assert r2.passive is True and r2.agent_span == cp.UNDEFINED and r2.object_key == "request"

    def test_a_finite_conjunct_with_its_own_subject_does_not_inherit_the_modal(self):
        """'The agency must respond, and the judge granted the motion' -- the
        second clause is a plain past event. Mutation: inherit the aux chain
        regardless of an own subject -> grant reads obligation (and writes a
        ledger row the text never stated; the refuter's must)."""
        assert one("The agency must respond, and the judge granted the motion.", "grant").modality == "event"
        assert one("Complainants can appeal, and the agency dismissed the case.", "dismiss").modality == "event"
        # the control: a subjectless conjunct still shares the modal
        assert one("The Commission could adopt, reject, or modify the recommendation.", "modify").modality == "conditional"

    def test_whether_is_a_marker_not_a_condition(self):
        """An interrogative complement is not conditional; 'whether' rides as
        a contrast marker only. Mutation: put whether back in _IF_MARKS."""
        r = one("The judge asked whether the agency responded.", "respond")
        assert r.modality != "conditional" and "whether" in r.contrast_span

    def test_no_on_the_subject_is_a_negation(self):
        """'No agency responded' negates the clause as 'no statement' does.
        Mutation: scan the object's determiner only -> False."""
        assert one("No agency responded to the complaint.", "respond").negation is True


# ---------------------------------------------------------------------------
# reading order + the stamp
# ---------------------------------------------------------------------------
class TestReadingOrderAndVersion:
    def test_rows_come_out_in_sentence_then_verb_order(self):
        """The reading-order refuter's predicate over the parser's own output.
        Mutation: sort by verb_idx alone -> a later sentence's early verb
        jumps ahead."""
        rs = rows("The agency appealed. I filed complaints, but the judge dismissed them. VA shared records.")
        assert cp.rows_in_reading_order(rs) is True
        assert [r.sentence_idx for r in rs] == sorted(r.sentence_idx for r in rs)
        assert cp.rows_in_reading_order(list(reversed(rs))) is False

    def test_the_stamp_names_the_pins(self):
        """PARSER_VERSION carries the two exact pins and the loaded model
        matches them. Mutation: bump the pin string without the wheel."""
        assert "spacy-3.8.14" in cp.PARSER_VERSION and "en_core_web_sm-3.8.0" in cp.PARSER_VERSION
        info = cp.warm()
        assert info["loaded"] is True and info["version"] == cp.PARSER_VERSION
        assert spacy.__version__ == "3.8.14"
        assert cp._nlp().meta["version"] == "3.8.0"
