"""
elins_operator_fusion.py — ELINS12 Unit 32.

Operator fusion actions on top of Unit 31's multi-regime temporal
fusion engine. Three helpers that turn a long-arc reading into
campaign-level action (decision + long-arc tags) or distribution
(structured long-arc report), plus an override surface for manual
operator decisions at the long-arc level.

ROLE
----
Final long-arc operator surface — converts cross-regime structural
behaviour into a single block / warn / allow verdict for an entire
campaign or release train. Pure composition over Unit 31. Tag
mutations are dedupe-aware and idempotent; overrides leave the
underlying fusion intact.

DECISION RULES (locked, deterministic)
--------------------------------------
    block  if  long_arc_assessment == "persistent_degradation"
           or  long_arc_assessment == "persistent_risk"
           or  (cumulative_risk.risk_level == "high"
                 AND oscillation.whipsaw == True)

    warn   if  long_arc_assessment == "oscillating_regime"
           or  cumulative_risk.risk_level == "medium"

    allow  otherwise

TAG VOCABULARY (locked)
-----------------------
Trajectory (exactly one fires):
    "trajectory_improving"
    "trajectory_degrading"
    "trajectory_flat"
    "trajectory_oscillating"

Long-arc assessment (exactly one fires):
    "long_arc_stabilizing"
    "long_arc_persistent_degradation"
    "long_arc_persistent_risk"
    "long_arc_oscillating_regime"
    "long_arc_benign"

Risk (exactly one fires):
    "long_arc_risk_low"
    "long_arc_risk_medium"
    "long_arc_risk_high"

Oscillation (optional — fires when applicable):
    "long_arc_oscillating"   (oscillation.is_oscillating)
    "long_arc_whipsaw"       (oscillation.whipsaw)

PUBLIC API
----------
    evaluate_long_arc(history)              -> dict
    generate_long_arc_report(history)       -> dict
    tag_long_arc_decisions(fusion, decisions) -> dict
"""
from __future__ import annotations

from elins_regime_fusion import fuse_regime_history


# Locked tag vocabulary — trajectory.
TAG_TRAJECTORY_IMPROVING:   str = "trajectory_improving"
TAG_TRAJECTORY_DEGRADING:   str = "trajectory_degrading"
TAG_TRAJECTORY_FLAT:        str = "trajectory_flat"
TAG_TRAJECTORY_OSCILLATING: str = "trajectory_oscillating"

# Locked tag vocabulary — long-arc assessment.
TAG_LA_STABILIZING:             str = "long_arc_stabilizing"
TAG_LA_PERSISTENT_DEGRADATION: str = "long_arc_persistent_degradation"
TAG_LA_PERSISTENT_RISK:         str = "long_arc_persistent_risk"
TAG_LA_OSCILLATING_REGIME:      str = "long_arc_oscillating_regime"
TAG_LA_BENIGN:                  str = "long_arc_benign"

# Locked tag vocabulary — risk.
TAG_LA_RISK_LOW:    str = "long_arc_risk_low"
TAG_LA_RISK_MEDIUM: str = "long_arc_risk_medium"
TAG_LA_RISK_HIGH:   str = "long_arc_risk_high"

# Locked tag vocabulary — oscillation.
TAG_LA_OSCILLATING: str = "long_arc_oscillating"
TAG_LA_WHIPSAW:     str = "long_arc_whipsaw"

# Override-tag vocabulary.
TAG_LA_OVERRIDE_DECISION:   str = "long_arc_override_decision"
TAG_LA_OVERRIDE_ESCALATED:  str = "long_arc_override_escalated"

# Decision vocabulary.
_DECISION_ALLOW: str = "allow"
_DECISION_WARN:  str = "warn"
_DECISION_BLOCK: str = "block"
_VALID_DECISIONS: tuple = (_DECISION_ALLOW, _DECISION_WARN, _DECISION_BLOCK)

# Lookup tables.
_TRAJECTORY_TAG_MAP: dict = {
    "improving":   TAG_TRAJECTORY_IMPROVING,
    "degrading":   TAG_TRAJECTORY_DEGRADING,
    "flat":        TAG_TRAJECTORY_FLAT,
    "oscillating": TAG_TRAJECTORY_OSCILLATING,
}

_ASSESSMENT_TAG_MAP: dict = {
    "stabilizing":             TAG_LA_STABILIZING,
    "persistent_degradation":  TAG_LA_PERSISTENT_DEGRADATION,
    "persistent_risk":         TAG_LA_PERSISTENT_RISK,
    "oscillating_regime":      TAG_LA_OSCILLATING_REGIME,
    "benign":                  TAG_LA_BENIGN,
}

_RISK_TAG_MAP: dict = {
    "low":    TAG_LA_RISK_LOW,
    "medium": TAG_LA_RISK_MEDIUM,
    "high":   TAG_LA_RISK_HIGH,
}

# Required Unit 31 fusion keys.
_REQUIRED_FUSION_KEYS: tuple = (
    "trajectory",
    "oscillation",
    "cumulative_risk",
    "long_arc_assessment",
)


def _validate_history_shape(history, fn_name: str) -> None:
    if not isinstance(history, list):
        raise ValueError(
            f"{fn_name} expected history to be a list, "
            f"got {type(history).__name__}"
        )


def _validate_fusion(fusion) -> None:
    if not isinstance(fusion, dict):
        raise ValueError(
            f"fusion must be a dict (Unit 31 output), "
            f"got {type(fusion).__name__}"
        )
    for key in _REQUIRED_FUSION_KEYS:
        if key not in fusion:
            raise ValueError(
                f"fusion missing required Unit 31 key {key!r}"
            )


def _validate_decision(decision, label: str) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"{label} must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _decision_for_fusion(fusion: dict) -> str:
    """Apply the locked decision rules over a Unit 31 fusion payload."""
    assessment = fusion["long_arc_assessment"]
    risk_level = fusion["cumulative_risk"].get("risk_level", "low")
    whipsaw = bool(fusion["oscillation"].get("whipsaw", False))
    if assessment in ("persistent_degradation", "persistent_risk"):
        return _DECISION_BLOCK
    if risk_level == "high" and whipsaw:
        return _DECISION_BLOCK
    if assessment == "oscillating_regime" or risk_level == "medium":
        return _DECISION_WARN
    return _DECISION_ALLOW


def _tags_for_fusion(fusion: dict) -> list:
    """Build the locked tag list from a Unit 31 fusion payload —
    alpha-sorted and deduped."""
    direction = fusion["trajectory"].get("dominant_direction", "flat")
    assessment = fusion["long_arc_assessment"]
    risk_level = fusion["cumulative_risk"].get("risk_level", "low")
    osc = fusion["oscillation"]

    tags: set = {
        _TRAJECTORY_TAG_MAP.get(direction, TAG_TRAJECTORY_FLAT),
        _ASSESSMENT_TAG_MAP.get(assessment, TAG_LA_BENIGN),
        _RISK_TAG_MAP.get(risk_level, TAG_LA_RISK_LOW),
    }
    if osc.get("is_oscillating"):
        tags.add(TAG_LA_OSCILLATING)
    if osc.get("whipsaw"):
        tags.add(TAG_LA_WHIPSAW)
    return sorted(tags)


def evaluate_long_arc(history) -> dict:
    """Evaluate Unit 31 and emit a long-arc decision + tags + fusion.

    Args:
        history: time-ordered list (oldest → newest) of Unit 29
            comparison outputs.

    Returns:
        ``{
            "decision":  "allow | warn | block",
            "tags":      list[str],   # alpha-sorted
            "fusion":    <full Unit 31 output>,
        }``.

    Raises:
        ValueError on a malformed history (forwarded from Unit 31).
    """
    _validate_history_shape(history, "evaluate_long_arc")
    fusion = fuse_regime_history(history)
    decision = _decision_for_fusion(fusion)
    tags = _tags_for_fusion(fusion)
    return {
        "decision":  decision,
        "tags":      tags,
        "fusion":    fusion,
    }


def _empty_report() -> dict:
    """Locked-shape placeholder for empty history."""
    fusion = fuse_regime_history([])
    return {
        "headline":            "No comparisons supplied for long-arc evaluation.",
        "decision":            _DECISION_ALLOW,
        "long_arc_assessment": "benign",
        "risk_level":          "low",
        "trajectory":          fusion["trajectory"],
        "oscillation":         fusion["oscillation"],
        "cumulative_risk":     fusion["cumulative_risk"],
        "fusion":              fusion,
        "history":             [],
    }


def _headline_for_long_arc(decision: str, fusion: dict) -> str:
    """Headline format (locked, matching spec example):

        "BLOCK: Persistent degradation with high long-arc risk
         (whipsaw regime; 4 high-risk segments over 12 comparisons)."
    """
    assessment = fusion["long_arc_assessment"]
    risk_level = fusion["cumulative_risk"].get("risk_level", "low")
    high_count = int(fusion["cumulative_risk"].get("high_count", 0))
    history_len = len(fusion.get("history", []))
    whipsaw = bool(fusion["oscillation"].get("whipsaw", False))
    is_osc = bool(fusion["oscillation"].get("is_oscillating", False))

    assessment_phrase = {
        "persistent_degradation": "Persistent degradation",
        "stabilizing":            "Stabilizing trajectory",
        "oscillating_regime":     "Oscillating regime",
        "persistent_risk":        "Persistent risk",
        "benign":                 "Benign long-arc",
    }.get(assessment, assessment.capitalize())

    if whipsaw:
        osc_phrase = "whipsaw regime"
    elif is_osc:
        osc_phrase = "oscillating regime"
    else:
        osc_phrase = "no oscillation"

    return (
        f"{decision.upper()}: {assessment_phrase} "
        f"with {risk_level} long-arc risk "
        f"({osc_phrase}; "
        f"{high_count} high-risk segments over {history_len} comparisons)."
    )


def generate_long_arc_report(history) -> dict:
    """Bundle Units 29 + 31 + 32 into an operator-facing long-arc
    report.

    Args:
        history: time-ordered list of Unit 29 comparison outputs.

    Returns:
        Locked-shape dict::

            {
              "headline":            str,
              "decision":            "allow | warn | block",
              "long_arc_assessment": <Unit 31 assessment>,
              "risk_level":          "low | medium | high",
              "trajectory":          <Unit 31 trajectory>,
              "oscillation":         <Unit 31 oscillation>,
              "cumulative_risk":     <Unit 31 cumulative_risk>,
              "fusion":              <full Unit 31 output>,
              "history":             <original Unit 29 comparisons>,
            }

        Empty history returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed history.
    """
    _validate_history_shape(history, "generate_long_arc_report")
    if not history:
        return _empty_report()

    evaluation = evaluate_long_arc(history)
    fusion = evaluation["fusion"]
    headline = _headline_for_long_arc(evaluation["decision"], fusion)
    return {
        "headline":            headline,
        "decision":            evaluation["decision"],
        "long_arc_assessment": fusion["long_arc_assessment"],
        "risk_level":          fusion["cumulative_risk"].get(
            "risk_level", "low",
        ),
        "trajectory":          fusion["trajectory"],
        "oscillation":         fusion["oscillation"],
        "cumulative_risk":     fusion["cumulative_risk"],
        "fusion":              fusion,
        "history":             list(history),
    }


def tag_long_arc_decisions(fusion, decisions) -> dict:
    """Apply caller-supplied overrides + tags to a Unit 31 fusion.

    Supported override keys (all optional):

        "override_decision": str   — replace the derived long-arc
                                     decision with an explicit
                                     "allow / warn / block". Adds
                                     the ``long_arc_override_decision``
                                     audit tag plus the matching
                                     risk-tier tag.
        "escalate":          bool  — when True, append the
                                     ``long_arc_override_escalated``
                                     tag.
        "audit_note":        str   — echoed in the response's
                                     ``overrides`` block for audit
                                     trails; does not generate a tag.

    Args:
        fusion: full Unit 31 ``fuse_regime_history`` output (or any
            dict matching its locked contract).
        decisions: dict of override / audit / escalation directives.
            Empty dict is allowed and is a no-op apart from the
            base fusion-derived tags.

    Returns:
        ``{
            "applied":   True,
            "tags":      list[str],   # alpha-sorted, deduped
            "overrides": dict,        # echo of the validated overrides
        }``.

    Raises:
        ValueError on a malformed fusion or decisions dict.
    """
    _validate_fusion(fusion)
    if not isinstance(decisions, dict):
        raise ValueError(
            f"tag_long_arc_decisions expected decisions to be a dict, "
            f"got {type(decisions).__name__}"
        )

    base_tags = set(_tags_for_fusion(fusion))
    overrides: dict = {}

    if "override_decision" in decisions:
        ov = decisions["override_decision"]
        _validate_decision(ov, "decisions['override_decision']")
        overrides["override_decision"] = ov
        base_tags.add(TAG_LA_OVERRIDE_DECISION)
        decision_tier_tag = {
            _DECISION_ALLOW: TAG_LA_RISK_LOW,
            _DECISION_WARN:  TAG_LA_RISK_MEDIUM,
            _DECISION_BLOCK: TAG_LA_RISK_HIGH,
        }[ov]
        base_tags.add(decision_tier_tag)

    if "escalate" in decisions:
        esc = decisions["escalate"]
        if not isinstance(esc, bool):
            raise ValueError(
                f"decisions['escalate'] must be a bool, "
                f"got {type(esc).__name__}"
            )
        overrides["escalate"] = esc
        if esc:
            base_tags.add(TAG_LA_OVERRIDE_ESCALATED)

    if "audit_note" in decisions:
        note = decisions["audit_note"]
        if not isinstance(note, str):
            raise ValueError(
                f"decisions['audit_note'] must be a string, "
                f"got {type(note).__name__}"
            )
        overrides["audit_note"] = note

    return {
        "applied":   True,
        "tags":      sorted(base_tags),
        "overrides": overrides,
    }
