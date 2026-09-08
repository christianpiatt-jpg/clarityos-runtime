"""
conversation_mode.py -- the shadow's counts -> ConversationMode (#133, step 2).

WHAT THIS IS. language_schemas.ConversationMode is "the cognitive register
of the current turn", and nothing on any production path classified it
(K3 MAP B, 2026-09-04): it was the one field the Primitive Selection
Engine reads that had NO producer. This module is that producer, in the
shadow: a deterministic rule table over counts the emophysics shadow
already logs per member turn (app.py _emophysics_shadow) -- D/N/T, the
P-series counts, and the seven grammar counters G1..G7 (#135).

WHAT IT IS NOT. Not NLP. The counts are regex + lexicon heuristics
(primitives_extract.py's own honesty note applies), so the mode is a
heuristic over heuristics, and it is logged, never acted on (#133:
acted_on:false everywhere). The thresholds are PRIORS, on record here so a
later ruling costs one line.

THE TABLE. First match wins. Register signals (an evaluation, a stated
intent, hedging) come before topic signals (structural terms, an abstract
agent), because the schema says mode is the REGISTER of the turn, and a
hedged diagnosis is exploratory before it is structural. A rule fires
when every count it reads is a real number (an int or a float, never a
bool, never the shadow's "UNMAPPED" sentinel) and their sum reaches the
threshold. No rule fires -> None, with the reason UNCLASSIFIED; the
caller then logs the plan as ABSENT. OPERATOR is never produced (#133:
"Never 'operator'"), asserted at import.

INVARIANTS (test-enforced, tests/test_conversation_mode.py):
    * Pure. No I/O, no randomness, no text -- the payload is counts.
    * Same payload -> same (mode, rule) tuple.
    * A bool or a non-number never counts toward a threshold.
    * No rule maps to ConversationMode.OPERATOR.
"""
from __future__ import annotations

from typing import Optional, Tuple

from language_schemas import ConversationMode

#: The reason a turn gets no mode. The shadow's plan line carries it verbatim.
UNCLASSIFIED: str = "conversation_mode unclassified"

#: (rule id, mode, the counts it reads, threshold on their sum, why).
#: Each entry names the payload keys it reads; "counts.Ts" walks one level
#: into the shadow's P-series counts dict. Order is precedence.
MODE_RULES: tuple = (
    ("R1", ConversationMode.EMOTIONAL, ("G5",), 1,
     "an objectless evaluation ('that is unacceptable') asserts a judgment "
     "with no object: the felt register"),
    ("R2", ConversationMode.DECISION, ("G7",), 1,
     "first-person intent about how something should land ('I want this "
     "to read well'): a forward commitment"),
    ("R3", ConversationMode.EXPLORATORY, ("T",), 0.5,
     "hedges per sentence at one in two or more: thinking aloud (T is the "
     "shadow's hedge ratio; UNMAPPED never fires)"),
    ("R4", ConversationMode.STRUCTURAL, ("counts.Ts", "counts.hydronic"), 2,
     "structural tensions and hydronic terms name a system being diagnosed"),
    ("R5", ConversationMode.STRUCTURAL, ("G3",), 1,
     "a non-local agent acting ('the market demands'): a structure "
     "described as an actor"),
)


def _number(payload: dict, key: str):
    """The value at ``key`` if it is a real number, else None.

    ``counts.Ts`` walks one level. A bool is not a count (True == 1 in
    Python, and G4_reflexive_only rides the same payload). The shadow's
    "UNMAPPED" sentinel is a string and never counts.
    """
    node = payload
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return node


def _fires(payload: dict, reads: tuple, threshold) -> bool:
    total = 0
    for key in reads:
        v = _number(payload, key)
        if v is None:
            return False
        total += v
    return total >= threshold


def classify(payload) -> Tuple[Optional[ConversationMode], str]:
    """The mode for one shadow payload, and the rule that produced it.

    Returns ``(mode, "R4 · counts.Ts + counts.hydronic >= 2")`` for the
    first rule that fires, or ``(None, UNCLASSIFIED)`` when none does.
    A non-dict payload classifies nothing.
    """
    if not isinstance(payload, dict):
        return None, UNCLASSIFIED
    for rule_id, mode, reads, threshold, _why in MODE_RULES:
        if _fires(payload, reads, threshold):
            return mode, "%s · %s >= %s" % (rule_id, " + ".join(reads), threshold)
    return None, UNCLASSIFIED


def _assert_never_operator() -> None:
    """#133: the shadow never labels a member turn OPERATOR. Import-time
    guard, the way language_schemas guards its derivation contract."""
    for rule_id, mode, _reads, _threshold, _why in MODE_RULES:
        assert mode is not ConversationMode.OPERATOR, rule_id


_assert_never_operator()
