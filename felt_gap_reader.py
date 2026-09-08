"""
felt_gap_reader.py · Layer-B first-cut classifier · Component A Ruling C1

Reads over-turn felt-gap signal from user's next-reply after assistant reply.
Deterministic. Zero LLM. Label-only. Fail-soft.

Under CT-1 · claim-of-shape · not claim-of-correctness.
Under Standing Truth · classifier does not work until live turns show otherwise.

Cross-witness: COW-1 §1.A PASS + §1.B PASS 7/7 + §1.C PASS-WITH-CAVEATS
              (substring caveat fixed · re-audit PASS 5/5 by execution 2026-07-30_1031EDT)
"""

import re
import time

# #163 (CT-1 2026-09-08): the record carries LABELS and a SEQ, never text.
# v0.1 stored the member's prompt and the assistant's reply beside the
# labels; no route ever read them. Bumped so an old row is recognisable.
READER_VERSION = "v0.2_enums_only"
RECORD_CLASS = "arc_record"   # #51 -- the record names its class

# Every key one arc_record carries. NO TEXT KEY, EVER. The route that
# serves them (app.py /me/relationships/{tid}/arc) allowlists a subset of
# these; tests/test_arc_reads_back.py pins this tuple to the builder's
# output and to the route's allowlist.
ARC_RECORD_KEYS = (
    "class", "correction_type", "felt_gap", "confidence", "delta_m", "arc",
    "reader_version", "assistant_seq", "made_turn", "user_next_reply_present",
    "ts_sealed",
)

FIRST_N_TOKENS = 60

CORRECT_TOKENS = frozenset({
    "no",
    "not quite",
    "actually",
    "instead",
    "meant",
    "rather",
    "wrong",
    "incorrect",
    "let me clarify",
    "what i meant",
    "to be clear",
    "that's not",
    "thats not",
    "not what",
    "you missed",
    "misunderstood",
    "misread",
})

BACK_AND_FORTH_TOKENS = frozenset({
    "why",
    "how",
    "what if",
    "can you",
    "could you",
    "would you",
    "why not",
    "how come",
    "what about",
    "but",
    "and if",
    "explain",
    "clarify",
    "expand",
    "elaborate",
    "tell me more",
})

ACCEPT_TOKENS = frozenset({
    "thanks",
    "thank you",
    "great",
    "perfect",
    "yes",
    "yep",
    "ok",
    "okay",
    "got it",
    "sounds good",
    "makes sense",
    "understood",
    "right",
    "agreed",
    "exactly",
})


def classify_correction_type(user_next_reply_text, user_next_reply_present):
    """
    Read user's next-reply opening · return correction-type label.
    Over-turns: reads only user_next_reply_text.
    Fail-soft: never raises · always returns valid label.
    Word-level matching for single-word tokens · substring for multi-word phrases.

    Returns one of: 'accept', 'correct', 'back_and_forth', 'unknown'
    """
    if not isinstance(user_next_reply_text, str):
        return "unknown"
    if not user_next_reply_present or not user_next_reply_text:
        return "unknown"

    text = user_next_reply_text.strip().lower()
    if not text:
        return "unknown"

    words = re.findall(r"[a-z']+", text)[:FIRST_N_TOKENS]
    if not words:
        return "unknown"
    word_set = set(words)
    opening = " ".join(words)

    for phrase in CORRECT_TOKENS:
        if " " in phrase:
            if phrase in opening:
                return "correct"
        else:
            if phrase in word_set:
                return "correct"

    for phrase in BACK_AND_FORTH_TOKENS:
        if " " in phrase:
            if phrase in opening:
                return "back_and_forth"
        else:
            if phrase in word_set:
                return "back_and_forth"

    for phrase in ACCEPT_TOKENS:
        if " " in phrase:
            if phrase in opening:
                return "accept"
        else:
            if phrase in word_set:
                return "accept"

    return "unknown"


def felt_gap_from_correction_type(correction_type):
    """Map correction-type label → felt-gap label. Pure lookup · no arithmetic."""
    return {
        "accept": "aligned",
        "correct": "misaligned",
        "back_and_forth": "unresolved",
        "unknown": "unmeasured",
    }[correction_type]


def confidence_from_correction_type(correction_type):
    """Map correction-type label → confidence label. Pure lookup · no arithmetic."""
    return {
        "accept": "held",
        "correct": "dropped",
        "back_and_forth": "provisional",
        "unknown": "null",
    }[correction_type]


def build_arc_record(
    user_id,
    thread_id,
    assistant_seq,
    user_prompt_text,
    assistant_reply_text,
    user_next_reply_text,
    user_next_reply_present,
):
    """
    Build one arc_record for a completed (or trailing-pending) turn pair.
    Written by the kernel to memory_vault key arc_records.{thread_id}.{seq:06d}.
    Own-namespace write-only · read-only threads_vault · fixture exclusion enforced upstream at seam.

    #163: the three text parameters are READ (the classifier reads
    user_next_reply_text; the other two are accepted for the call's shape)
    and NONE is stored. ``made_turn`` is the assistant_seq the arc was made
    on, so a reader can say "made turn a · now turn b" -- age in TURNS,
    never a clock (ts_sealed is a stamp, not an age).
    """
    correction_type = classify_correction_type(user_next_reply_text, user_next_reply_present)
    felt_gap = felt_gap_from_correction_type(correction_type)
    confidence = confidence_from_correction_type(correction_type)

    return {
        "class": RECORD_CLASS,
        "correction_type": correction_type,
        "felt_gap": felt_gap,
        "confidence": confidence,
        "delta_m": None,
        "arc": None,
        "reader_version": READER_VERSION,
        "assistant_seq": int(assistant_seq),
        "made_turn": int(assistant_seq),
        "user_next_reply_present": bool(user_next_reply_present),
        "ts_sealed": time.time(),
    }
