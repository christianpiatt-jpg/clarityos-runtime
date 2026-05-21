"""
v33 — Most Relevant Comment Generator (MRCG v1.0).

Three-layer pipeline that produces a short, low-emotion, high-signal
comment for a given input. Intended for the founder-only
``#cmt`` engine and the public-facing comment-suggestion surface.

    LAYER 1 — DETECTION
        attractor + domain vector + emotional tone

    LAYER 2 — CONSTRUCTION
        Structural Reframe + Domain Alignment +
        ClarityOS Identity Move + Stabilizing Close

    LAYER 3 — ACTIVATION
        micro-thread trigger + low-emotion constraint +
        high-signal noun density check

The implementation is deterministic + lexical: same input + same
domain hint always produce the same comment. No model calls, no
network. Output shape is stable; tests pin per-attractor templates
and the assembled comment string.

Public API:

    generate_comment(input_text, domain_hint=None) -> dict
        Returns a flat record:
            {
              "ok": True,
              "comment": str,            # the assembled comment
              "detection": {...},
              "construction": {...},     # 4 named segments
              "activation": {...},       # micro_thread / tone / noun_density
              "version": "mrcg.v1.0",
            }

    generate_structural_reframe(detection) -> str
    generate_domain_alignment(detection) -> str
    generate_identity_move(detection) -> str
    generate_stabilizing_close(detection) -> str
"""
from __future__ import annotations

import re
import time
from typing import Optional

# Reuse the ELINS lexical layer so the detection feels in-family.
from ELINS import standard_elins as se

VALID_ATTRACTORS: tuple = (
    "institutional_drift",
    "trust_collapse",
    "contradiction",
    "consensus_drift",
    "stabilising_pressure",
    "neutral",
)

VALID_TONES: tuple = (
    "alarmed",
    "frustrated",
    "analytical",
    "hopeful",
    "neutral",
)

# Per-attractor, per-domain phrase templates. Kept small + bounded.
# Templates use {domain} substitution; missing domain falls back to
# the attractor's "default" entry.
_REFRAME: dict[str, dict[str, str]] = {
    "institutional_drift": {
        "default": "The visible breakdown is downstream of an institution drifting from its mandate.",
        "legal": "The legal surface is reacting; the load is on the institution behind it.",
        "institutional": "The visible breakdown is downstream of an institution drifting from its mandate.",
        "economic": "The market motion is reacting; the load is on the institution managing the framework.",
        "geopolitical": "The geopolitical surface is reacting; the load is on the institution underwriting it.",
    },
    "trust_collapse": {
        "default": "The visible noise is the trust layer thinning, not the surface argument.",
        "social": "What looks like a public argument is the trust layer thinning underneath it.",
        "institutional": "The institutional reaction is downstream of a trust gap, not vice versa.",
    },
    "contradiction": {
        "default": "Two stated goals here are pulling in opposite directions; the system is not asking which one is true.",
        "legal": "Two stated legal principles are pulling in opposite directions; one will give first.",
        "geopolitical": "Two stated commitments are at odds; one will give first.",
    },
    "consensus_drift": {
        "default": "What reads as agreement is converging on a moving target — the consensus is drifting under it.",
    },
    "stabilising_pressure": {
        "default": "The pressure is increasing the cost of the current arrangement, not threatening it.",
    },
    "neutral": {
        "default": "Most of the heat in the surface argument isn't where the load actually sits.",
    },
}

_DOMAIN_ALIGN: dict[str, str] = {
    "legal":          "In legal terms: the surface ruling buys time but does not resolve the underlying claim.",
    "institutional":  "In institutional terms: the agency is absorbing pressure that belongs upstream.",
    "economic":       "Economically: the price action is downstream of a structural mismatch, not the cause of it.",
    "geopolitical":   "Geopolitically: the visible move is a signal in a longer alignment shift.",
    "social":         "Socially: the loud part is downstream of a quieter trust shift.",
    "personal":       "On the personal layer: the visible reaction is an indicator, not the load itself.",
    "technological":  "Technologically: the platform reaction is downstream of an unresolved design choice.",
    "ecological":     "Ecologically: the visible event is a tail of a longer-running structural pressure.",
}

_IDENTITY_MOVE: dict[str, str] = {
    "institutional_drift": (
        "ClarityOS reads the institution's drift as the operative variable — "
        "not the news cycle around it."
    ),
    "trust_collapse": (
        "ClarityOS treats trust density as the load-bearing layer; "
        "rebuilding it is a different motion than winning the argument."
    ),
    "contradiction": (
        "ClarityOS surfaces the contradiction without forcing a resolution — "
        "the system has to pick which goal is real."
    ),
    "consensus_drift": (
        "ClarityOS notes the consensus is drifting; "
        "treating today's agreement as the same as last quarter's is the trap."
    ),
    "stabilising_pressure": (
        "ClarityOS reads the pressure as load on a frame, not as a threat to it."
    ),
    "neutral": (
        "ClarityOS keeps the structural read separate from the surface noise."
    ),
}

_STABILISING_CLOSE: dict[str, str] = {
    "alarmed":     "Worth watching; not worth panicking about yet.",
    "frustrated":  "The frustration is fair; the load it's pointing at is upstream.",
    "analytical":  "The next data point won't resolve this; the structural read does.",
    "hopeful":     "Hopeful, with the caveat that the structural load hasn't moved yet.",
    "neutral":     "Worth holding the structural read while the surface keeps moving.",
}

# Tone lexicon — same shape as the ELINS lexicon.
_TONE_LEXICON: dict[str, list[str]] = {
    "alarmed":    ["danger", "alarm", "frighten", "scary", "horrifying",
                   "catastroph", "panic"],
    "frustrated": ["frustrat", "tired of", "fed up", "angry", "outrage",
                   "infuriat", "absurd"],
    "analytical": ["data", "according to", "evidence", "statistic",
                   "metrics", "measure", "study"],
    "hopeful":    ["hope", "optimist", "promising", "encouraging",
                   "improving", "better"],
}


# ---------------------------------------------------------------------------
# Layer 1 — DETECTION
# ---------------------------------------------------------------------------
def _detect_attractor(intensities: dict) -> str:
    """Choose an attractor based on which primitive(s) dominate. The
    decision is purely deterministic: highest-intensity primitive wins,
    with mapped names for the spec's attractor vocabulary."""
    if not intensities:
        return "neutral"
    # Map each primitive to an attractor candidate; tied scores resolve
    # alphabetically for determinism.
    mapping = {
        "pressure": "institutional_drift",
        "tension": "contradiction",
        "trust": "trust_collapse",
        "drift": "institutional_drift",
        "contradiction": "contradiction",
        "alignment": "consensus_drift",
    }
    # Trust collapse fires on LOW trust + present tension/contradiction
    # rather than on high trust intensity — flip the mapping for that
    # primitive so the lexical "trust" hit alone doesn't trigger it.
    sorted_pairs = sorted(
        intensities.items(), key=lambda kv: (-kv[1], kv[0]),
    )
    top, top_val = sorted_pairs[0]
    if top_val < 0.05:
        return "neutral"
    if top == "trust":
        # High trust signal alone is a stabilising read.
        return "stabilising_pressure"
    return mapping.get(top, "neutral")


def _detect_tone(text: str) -> str:
    text_lower = text.lower()
    best = ("neutral", 0)
    for tone, tokens in _TONE_LEXICON.items():
        hits = sum(text_lower.count(t) for t in tokens)
        if hits > best[1]:
            best = (tone, hits)
    return best[0]


def _detect(input_text: str, domain_hint: Optional[str]) -> dict:
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("input_text must be a non-empty string")
    text = input_text.strip()
    primitives = se._layer_1_primitives(text)
    intensities = primitives["intensities"]
    domain_layer = se._layer_2_domains(text, domain_hint)
    domain = domain_layer.get("effective_top") or domain_hint or None
    attractor = _detect_attractor(intensities)
    tone = _detect_tone(text)
    return {
        "attractor": attractor,
        "domain": domain,
        "tone": tone,
        "primitive_intensities": intensities,
        "domain_scores": domain_layer.get("scores") or {},
        "input_word_count": len(text.split()),
    }


# ---------------------------------------------------------------------------
# Layer 2 — CONSTRUCTION
# ---------------------------------------------------------------------------
def generate_structural_reframe(detection: dict) -> str:
    attractor = detection.get("attractor") or "neutral"
    domain = detection.get("domain") or "default"
    table = _REFRAME.get(attractor) or _REFRAME["neutral"]
    return table.get(domain) or table.get("default") or _REFRAME["neutral"]["default"]


def generate_domain_alignment(detection: dict) -> str:
    domain = detection.get("domain")
    if domain and domain in _DOMAIN_ALIGN:
        return _DOMAIN_ALIGN[domain]
    return "Across domains: the surface motion is a signal, not the load."


def generate_identity_move(detection: dict) -> str:
    attractor = detection.get("attractor") or "neutral"
    return _IDENTITY_MOVE.get(attractor) or _IDENTITY_MOVE["neutral"]


def generate_stabilizing_close(detection: dict) -> str:
    tone = detection.get("tone") or "neutral"
    return _STABILISING_CLOSE.get(tone) or _STABILISING_CLOSE["neutral"]


# ---------------------------------------------------------------------------
# Layer 3 — ACTIVATION (constraints / metadata only, no rewriting)
# ---------------------------------------------------------------------------
_NOUN_RE = re.compile(r"[A-Za-z][A-Za-z\-]{3,}")


def _noun_density(text: str) -> float:
    """Approximate noun density — fraction of tokens 4+ chars long that
    aren't a function word. Crude but stable; a real NLP pass is out of
    v33 scope. Returns 0..1."""
    function_words = {
        "this", "that", "these", "those", "with", "from", "into", "onto",
        "their", "there", "where", "which", "while", "when", "without",
        "about", "after", "before", "below", "above", "again", "still",
        "could", "would", "should", "might", "shall",
    }
    tokens = [t.lower() for t in _NOUN_RE.findall(text)]
    if not tokens:
        return 0.0
    nouns = [t for t in tokens if t not in function_words]
    return round(len(nouns) / len(tokens), 4)


def _has_low_emotion(text: str) -> bool:
    """The constructed comment should keep the emotional tone low. We
    approximate by counting hits in the alarmed + frustrated lexicons
    and rejecting if more than 1 fires."""
    text_lower = text.lower()
    hot = 0
    for tone in ("alarmed", "frustrated"):
        hot += sum(text_lower.count(t) for t in _TONE_LEXICON[tone])
    return hot <= 1


def _activation(comment: str) -> dict:
    return {
        "micro_thread_trigger": "open_with_a_lens",   # canonical handle
        "low_emotion": _has_low_emotion(comment),
        "noun_density": _noun_density(comment),
        "char_count": len(comment),
        "version": "mrcg.activation.v1",
    }


# ---------------------------------------------------------------------------
# Public — generate_comment
# ---------------------------------------------------------------------------
def generate_comment(input_text: str, domain_hint: Optional[str] = None) -> dict:
    """Run the full MRCG pipeline. Returns the assembled comment +
    detection + construction + activation metadata."""
    if domain_hint is not None and domain_hint not in se.DOMAIN_HINTS:
        raise ValueError(
            f"domain_hint must be one of {se.DOMAIN_HINTS!r}, got {domain_hint!r}"
        )
    detection = _detect(input_text, domain_hint)
    construction = {
        "structural_reframe": generate_structural_reframe(detection),
        "domain_alignment": generate_domain_alignment(detection),
        "identity_move": generate_identity_move(detection),
        "stabilizing_close": generate_stabilizing_close(detection),
    }
    comment = " ".join([
        construction["structural_reframe"],
        construction["domain_alignment"],
        construction["identity_move"],
        construction["stabilizing_close"],
    ])
    activation = _activation(comment)
    return {
        "ok": True,
        "comment": comment,
        "detection": detection,
        "construction": construction,
        "activation": activation,
        "version": "mrcg.v1.0",
        "ts": time.time(),
    }
