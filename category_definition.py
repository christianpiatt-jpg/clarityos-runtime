"""
category_definition.py — Phase 14 read-only category-definition layer.

Pure stdlib. Two public functions:

    describe_category()  -> dict
        Static description of the Inferential Discipline System (IDS)
        category: name, purpose, boundaries, differentiators,
        non-goals, allowed external moves.

    summarize_category() -> dict
        Combined structure suitable for a single founder dashboard.
        Carries the category description plus example external
        statements and notes[].

Contract per tests/acceptance/category_definition.md:
    - read-only;
    - never raises (returns empty dicts + descriptive notes on failure);
    - takes no parameters (the layer is purely taxonomic);
    - never persists.

Like Phase 13, the descriptions are deliberately stable. Update only
when the top-level taxonomy itself changes (e.g., a sixth structural
property is added to the category boundary).
"""
from __future__ import annotations

from typing import Any


_CATEGORY = {
    "name":         "Inferential Discipline System",
    "acronym":      "IDS",
    "instance":     "ClarityOS",
    "purpose": (
        "A reasoning runtime that carries a versioned, falsifiable "
        "contract; gates every inferential claim; retracts prior "
        "claims under stricter contracts without overwriting their "
        "evidence; surfaces its own posture, readiness, and continuity "
        "descriptively; and is operator-graded rather than user-graded."
    ),
    "structural_properties": [
        "gated — every inferential claim passes through documented gates",
        "contract-bound — gates are defined in a versioned, immutable contract",
        "falsifiable — patterns must survive a paired permutation null",
        "descriptive — surfaces report state; they do not enforce or automate",
        "operator-graded — built for the operator, not the end-user",
    ],
    "boundaries": [
        "no promises of outcomes",
        "no predictions of effectiveness",
        "no recommendations or rankings",
        "no automation across the operator boundary",
        "no conflation of descriptive output with prescriptive guidance",
    ],
    "differentiators": {
        "vs_productivity_tools": (
            "Productivity tools optimize action throughput; an IDS "
            "optimizes inferential honesty. The two are orthogonal — "
            "an IDS does not make you faster."
        ),
        "vs_ai_assistants": (
            "AI assistants generate content on demand. An IDS audits "
            "claims under a versioned, inspectable contract. An "
            "assistant without a contract is not an IDS, even if it "
            "is internally rigorous."
        ),
        "vs_coaching_frameworks": (
            "Coaching frameworks help the operator change themselves. "
            "An IDS audits the system. Posture is descriptive, not "
            "prescriptive — the IDS does not tell the operator what "
            "to do; it tells them what the state is."
        ),
        "vs_analytics_dashboards": (
            "Analytics dashboards surface KPIs. An IDS surfaces gate "
            "outcomes — which claims passed, which were retracted, "
            "why. KPIs without gates become decorative."
        ),
        "vs_mental_models": (
            "A mental model is a way of thinking. An IDS is runtime "
            "infrastructure that holds a way of thinking to a contract. "
            "The model fits in your head; the contract lives in the "
            "codebase."
        ),
    },
    "non_goals": [
        "make the operator faster",
        "generate content on the operator's behalf",
        "coach the operator on what to ship",
        "rank options or recommend choices",
        "replace mental models or frameworks the operator already holds",
    ],
}


_EXAMPLE_STATEMENTS = [
    {
        "kind": "definition",
        "text": (
            "ClarityOS is an Inferential Discipline System: it carries a "
            "versioned, falsifiable contract that retracts inferential "
            "claims when stricter gates fire — without overwriting the "
            "prior reading or the prior evidence."
        ),
    },
    {
        "kind": "boundary",
        "text": (
            "An IDS is not a productivity tool. It does not help you do "
            "things faster. It tells you when an inference does not hold "
            "and surfaces the gate that caught it. The operator decides "
            "what to do next."
        ),
    },
    {
        "kind": "posture",
        "text": (
            "What ClarityOS produces is a single read on whether your "
            "reasoning system is in a state where you can ship. The "
            "operator decides; the system surfaces. There is no gating "
            "of action, no automation, no prediction."
        ),
    },
]


_ALLOWED_EXTERNAL = [
    "describe the five structural properties",
    "name what the category is and is not",
    "quote the operator's own prior reading without prediction",
    "describe what the surfaces show",
    "describe what the contracts gate",
    "describe what the system refuses to do",
]


_DISALLOWED_EXTERNAL = [
    "promise outcomes",
    "predict success rates",
    "claim effectiveness without falsifiability",
    "describe the system as an assistant or a coach",
    "conflate descriptive output with prescriptive guidance",
]


def describe_category() -> dict:
    """Return the static description of the IDS category."""
    try:
        out: dict[str, Any] = {}
        for k, v in _CATEGORY.items():
            if isinstance(v, list):
                out[k] = list(v)
            elif isinstance(v, dict):
                out[k] = dict(v)
            else:
                out[k] = v
        return out
    except Exception:
        return {
            "name":     "Inferential Discipline System",
            "acronym":  "IDS",
            "instance": "ClarityOS",
            "purpose":  "no description available",
            "structural_properties": [],
            "boundaries":            [],
            "differentiators":       {},
            "non_goals":             [],
        }


def summarize_category() -> dict:
    """Return the combined founder-facing payload."""
    notes: list[str] = []
    try:
        category = describe_category()
    except Exception:
        category = {}
        notes.append("describe_category raised — returned empty")
    try:
        examples = [dict(s) for s in _EXAMPLE_STATEMENTS]
    except Exception:
        examples = []
        notes.append("example statements raised — returned empty")
    try:
        external = {
            "allowed":    list(_ALLOWED_EXTERNAL),
            "disallowed": list(_DISALLOWED_EXTERNAL),
        }
    except Exception:
        external = {"allowed": [], "disallowed": []}
        notes.append("external moves table raised — returned empty")
    return {
        "category":              category,
        "example_statements":    examples,
        "external_language":     external,
        "notes":                 notes,
    }
