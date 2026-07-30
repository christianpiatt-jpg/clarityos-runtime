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

READER_VERSION = "v0.1_phase1_first_cut"

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
    Written to arc_records/{user_id}/{thread_id}/{assistant_seq} in Firestore.
    Own-collection write-only · read-only threads_vault · fixture exclusion enforced upstream at seam.
    """
    correction_type = classify_correction_type(user_next_reply_text, user_next_reply_present)
    felt_gap = felt_gap_from_correction_type(correction_type)
    confidence = confidence_from_correction_type(correction_type)

    return {
        "e_t_user_prompt": user_prompt_text,
        "y_t_assistant_reply": assistant_reply_text,
        "correction_type": correction_type,
        "felt_gap": felt_gap,
        "confidence": confidence,
        "delta_m": None,
        "arc": None,
        "reader_version": READER_VERSION,
        "assistant_seq": assistant_seq,
        "user_next_reply_present": user_next_reply_present,
    }
