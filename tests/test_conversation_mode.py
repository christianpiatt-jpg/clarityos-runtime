"""
#133 step 2 -- the mode table.

WHAT THESE PIN. The table's shape and precedence, one fixture per rule,
the flat payload that classifies nothing, and the three ways a count must
NOT fire: a bool, the UNMAPPED sentinel, a value under the threshold. The
thresholds are priors; a change to one is a one-line change here too.
"""
from __future__ import annotations

import pytest

import conversation_mode as cm
from language_schemas import ConversationMode as M

SHADOW_KEYS = {"D", "N", "T", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "counts"}
COUNT_KEYS = {"P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"}


def _p(**kw):
    """A flat shadow payload (the shape app._emophysics_shadow logs), with
    overrides. ``counts=`` merges into the P-series dict."""
    base = {
        "D": 0, "N": "UNMAPPED", "T": 0.0,
        "counts": {k: 0 for k in COUNT_KEYS},
        "G1": 0, "G2": 0, "G3": 0, "G4": 0, "G5": 0, "G6": 0, "G7": 0,
        "G4_reflexive_only": True, "G_sentences": 1,
    }
    counts = kw.pop("counts", None)
    base.update(kw)
    if counts:
        base["counts"].update(counts)
    return base


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------
def test_the_table_never_produces_operator():
    assert all(mode is not M.OPERATOR for _id, mode, _r, _t, _w in cm.MODE_RULES)


def test_each_rule_has_an_id_a_mode_reads_a_threshold_and_a_why():
    ids = []
    for rule in cm.MODE_RULES:
        rule_id, mode, reads, threshold, why = rule
        assert isinstance(rule_id, str) and rule_id.startswith("R")
        assert isinstance(mode, M)
        assert isinstance(reads, tuple) and reads
        assert isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
        assert isinstance(why, str) and why
        ids.append(rule_id)
    assert len(ids) == len(set(ids))


def test_the_rules_read_only_keys_the_shadow_logs():
    for _id, _mode, reads, _t, _why in cm.MODE_RULES:
        for key in reads:
            head, _, tail = key.partition(".")
            assert head in SHADOW_KEYS, key
            if tail:
                assert head == "counts" and tail in COUNT_KEYS, key


# --------------------------------------------------------------------------
# one fixture per rule, and the flat turn
# --------------------------------------------------------------------------
def test_flat_payload_is_unclassified():
    assert cm.classify(_p()) == (None, cm.UNCLASSIFIED)


@pytest.mark.parametrize("payload,mode,rule_id", [
    (_p(G5=1), M.EMOTIONAL, "R1"),
    (_p(G7=1), M.DECISION, "R2"),
    (_p(T=0.5), M.EXPLORATORY, "R3"),
    (_p(counts={"Ts": 1, "hydronic": 1}), M.STRUCTURAL, "R4"),
    (_p(counts={"Ts": 2}), M.STRUCTURAL, "R4"),
    (_p(G3=1), M.STRUCTURAL, "R5"),
])
def test_one_rule_one_fixture(payload, mode, rule_id):
    got_mode, rule = cm.classify(payload)
    assert got_mode is mode
    assert rule.startswith(rule_id + " · ")
    assert ">=" in rule


def test_precedence_register_before_topic():
    """A hedged diagnosis is exploratory before it is structural; an
    evaluation under structural words is emotional first."""
    assert cm.classify(_p(G5=1, counts={"Ts": 5}))[0] is M.EMOTIONAL
    assert cm.classify(_p(T=1.0, counts={"Ts": 5}))[0] is M.EXPLORATORY
    assert cm.classify(_p(G7=1, T=1.0))[0] is M.DECISION


# --------------------------------------------------------------------------
# what never counts
# --------------------------------------------------------------------------
def test_unmapped_and_bools_never_count():
    assert cm.classify(_p(T="UNMAPPED")) == (None, cm.UNCLASSIFIED)
    assert cm.classify(_p(G5=True)) == (None, cm.UNCLASSIFIED)
    assert cm.classify(_p(counts={"Ts": True, "hydronic": True})) == (None, cm.UNCLASSIFIED)
    assert cm.classify(_p(G3="1")) == (None, cm.UNCLASSIFIED)


def test_below_threshold_does_not_fire():
    assert cm.classify(_p(T=0.49))[0] is None
    assert cm.classify(_p(counts={"Ts": 1}))[0] is None
    assert cm.classify(_p(counts={"hydronic": 1}))[0] is None


def test_a_missing_key_is_not_a_zero_that_fires_and_not_a_crash():
    assert cm.classify({})[0] is None
    assert cm.classify({"counts": "nope"})[0] is None
    assert cm.classify(None) == (None, cm.UNCLASSIFIED)
    assert cm.classify("G5=1") == (None, cm.UNCLASSIFIED)


def test_deterministic():
    p = _p(G5=1, T=0.7, counts={"Ts": 3})
    assert cm.classify(p) == cm.classify(dict(p))
