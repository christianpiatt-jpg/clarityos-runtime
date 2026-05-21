"""
elins_operator_structural.py — ELINS10 Unit 28.

Operator-facing workflows on top of Unit 27's structural-trend engine.
Three helpers that turn structural analysis into action (regime
verdict tags) or distribution (structured structural report).

ROLE
----
Operator workflow surface for long-arc structural intelligence. Pure
composition over Units 21 + 27. Tags map regime / volatility /
breakpoint state to the locked vocabulary documented below; tag
mutations are dedupe-aware and idempotent.

DECISION RULES (locked, deterministic)
--------------------------------------
    regime_class == "unstable"     → "block"
    regime_class == "transition"   → "warn"
    regime_class == "stable"       → "allow"

TAG VOCABULARY (locked)
-----------------------
Regime tags (exactly one fires per call):
    "regime_stable"
    "regime_transition"
    "regime_unstable"

Volatility tags (exactly one fires per call):
    "volatility_low"       — variance < 0.005
    "volatility_medium"    — 0.005 <= variance < 0.02
    "volatility_high"      — variance >= 0.02

Breakpoint tags (exactly one fires per call):
    "breakpoints_present"
    "no_breakpoints"

PUBLIC API
----------
    apply_structural_analysis(timeline) -> dict
    tag_structural_decisions(timeline, decision: str) -> dict
    generate_structural_report(timeline) -> dict
"""
from __future__ import annotations

from elins_structural_trend import analyze_structural_trends


# Locked tag vocabulary.
TAG_REGIME_STABLE:       str = "regime_stable"
TAG_REGIME_TRANSITION:   str = "regime_transition"
TAG_REGIME_UNSTABLE:     str = "regime_unstable"
TAG_VOLATILITY_LOW:      str = "volatility_low"
TAG_VOLATILITY_MEDIUM:   str = "volatility_medium"
TAG_VOLATILITY_HIGH:     str = "volatility_high"
TAG_BREAKPOINTS_PRESENT: str = "breakpoints_present"
TAG_NO_BREAKPOINTS:      str = "no_breakpoints"

# Variance buckets (mirror Unit 27).
_VAR_LOW_MAX:   float = 0.005
_VAR_HIGH_MIN:  float = 0.02

# Decision vocabulary.
_DECISION_ALLOW: str = "allow"
_DECISION_WARN:  str = "warn"
_DECISION_BLOCK: str = "block"
_VALID_DECISIONS: tuple = (_DECISION_ALLOW, _DECISION_WARN, _DECISION_BLOCK)

# Regime → decision map.
_REGIME_DECISION_MAP: dict = {
    "stable":     _DECISION_ALLOW,
    "transition": _DECISION_WARN,
    "unstable":   _DECISION_BLOCK,
}

# Regime → tag map.
_REGIME_TAG_MAP: dict = {
    "stable":     TAG_REGIME_STABLE,
    "transition": TAG_REGIME_TRANSITION,
    "unstable":   TAG_REGIME_UNSTABLE,
}


def _validate_timeline_shape(timeline, fn_name: str) -> None:
    if not isinstance(timeline, list):
        raise ValueError(
            f"{fn_name} expected timeline to be a list, "
            f"got {type(timeline).__name__}"
        )


def _validate_decision(decision, label: str) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"{label} must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _volatility_tag(variance: float) -> str:
    if variance >= _VAR_HIGH_MIN:
        return TAG_VOLATILITY_HIGH
    if variance < _VAR_LOW_MAX:
        return TAG_VOLATILITY_LOW
    return TAG_VOLATILITY_MEDIUM


def _breakpoint_tag(breakpoints: list) -> str:
    return TAG_BREAKPOINTS_PRESENT if breakpoints else TAG_NO_BREAKPOINTS


def _tags_for_structural(regime: str,
                          variance: float,
                          breakpoints: list) -> list:
    """Build the locked-vocabulary tag list. Alpha-sorted for
    deterministic operator rendering."""
    tags = [
        _REGIME_TAG_MAP.get(regime, TAG_REGIME_STABLE),
        _volatility_tag(variance),
        _breakpoint_tag(breakpoints),
    ]
    return sorted(tags)


def apply_structural_analysis(timeline) -> dict:
    """Evaluate Unit 27 and emit a decision + tags + raw structural
    signals.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples.

    Returns:
        ``{
            "decision":            "allow | warn | block",
            "tags":                list[str],   # alpha-sorted
            "regime_class":        <Unit 27 regime>,
            "volatility_variance": float,
            "breakpoints":         list[dict],
            "structural_events":   list[str],
        }``.

    Raises:
        ValueError on a malformed timeline (forwarded from Unit 27).
    """
    _validate_timeline_shape(timeline, "apply_structural_analysis")
    structural = analyze_structural_trends(timeline)
    regime = structural["regime_class"]
    decision = _REGIME_DECISION_MAP.get(regime, _DECISION_WARN)
    tags = _tags_for_structural(
        regime,
        float(structural["volatility_variance"]),
        structural["breakpoints"],
    )
    return {
        "decision":            decision,
        "tags":                tags,
        "regime_class":        regime,
        "volatility_variance": float(structural["volatility_variance"]),
        "breakpoints":         structural["breakpoints"],
        "structural_events":   structural["structural_events"],
    }


def tag_structural_decisions(timeline, decision: str) -> dict:
    """Apply a caller-supplied structural decision as tags.

    The structural regime is a property of the WHOLE timeline (unlike
    Unit 26's per-timestamp trend decisions). The signature therefore
    takes a single decision string.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples — validated through Unit 27 to ensure shape parity
            with the analysis path.
        decision: one of ``"allow"``, ``"warn"``, ``"block"``.

    Returns:
        ``{"applied": True, "tags": list[str]}`` — the tag list
        contains exactly one regime-level tag derived from the
        caller-supplied decision.

    Raises:
        ValueError on a malformed timeline or invalid decision.
    """
    _validate_timeline_shape(timeline, "tag_structural_decisions")
    _validate_decision(decision, "decision")
    # Run analyze_structural_trends to ensure timeline shape is valid —
    # we don't use the result, but bubbling Unit 27's validation keeps
    # the API contract honest.
    analyze_structural_trends(timeline)
    decision_tag_map = {
        _DECISION_ALLOW: TAG_REGIME_STABLE,
        _DECISION_WARN:  TAG_REGIME_TRANSITION,
        _DECISION_BLOCK: TAG_REGIME_UNSTABLE,
    }
    return {
        "applied": True,
        "tags":    [decision_tag_map[decision]],
    }


def _empty_report() -> dict:
    return {
        "headline":            "No batches supplied for structural analysis.",
        "regime_class":        "stable",
        "volatility_variance": 0.0,
        "breakpoints":         [],
        "structural_events":   ["insufficient_data"],
        "timeline":            [],
        "alerts":              {},
        "pairs":               {},
        "diffs":               {},
    }


def _alerts_for_batch(batch_payload: dict) -> list:
    """Per-batch alert aggregation (mirror Unit 24 / 26)."""
    alerts: list = []
    groups = batch_payload.get("groups", {}) or {}
    for group_name in sorted(groups.keys()):
        data = groups[group_name]
        decision = data.get("decision", "warn")
        if decision == "block":
            alerts.append({
                "type":     "blocked_group",
                "severity": "critical",
                "group":    group_name,
                "reasons":  list(data.get("reasons", [])),
            })
        elif decision == "warn":
            alerts.append({
                "type":     "warned_group",
                "severity": "warning",
                "group":    group_name,
                "reasons":  list(data.get("reasons", [])),
            })
    return alerts


def _pairs_for_batch(batch_payload: dict) -> list:
    seen: set = set()
    comparisons = batch_payload.get("comparisons", {}) or {}
    for entry in comparisons.values():
        for pid in entry.get("pair_regressions", []) or []:
            seen.add(pid)
    return sorted(seen)


def _diffs_for_batch(batch_payload: dict) -> dict:
    return dict(batch_payload.get("comparisons", {}) or {})


def _headline_for_structural(structural: dict, n_batches: int) -> str:
    """Compose a one-liner keyed off regime + breakpoint count."""
    regime = structural["regime_class"]
    variance = float(structural["volatility_variance"])
    breakpoints = structural["breakpoints"]

    if structural["structural_events"] == ["insufficient_data"]:
        return f"Insufficient data for structural analysis ({n_batches} batches)."

    vol_label = _volatility_tag(variance).replace("volatility_", "")
    n_bp = len(breakpoints)

    if regime == "unstable":
        return (
            f"UNSTABLE regime detected "
            f"(volatility {vol_label}; {n_bp} breakpoints)."
        )
    if regime == "transition":
        return (
            f"Transition regime across {n_batches} batches "
            f"(volatility {vol_label}; {n_bp} breakpoints)."
        )
    return (
        f"Stable regime across {n_batches} batches "
        f"(no breakpoints; volatility {vol_label})."
    )


def generate_structural_report(timeline) -> dict:
    """Bundle Units 21 + 27 (with per-timestamp alert / pair / diff
    aggregates) into a locked-shape report.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples.

    Returns:
        Locked-shape dict::

            {
              "headline":            str,
              "regime_class":        <Unit 27 regime>,
              "volatility_variance": float,
              "breakpoints":         list[dict],
              "structural_events":   list[str],
              "timeline":            <Unit 27 timeline>,
              "alerts":              {timestamp: [<alert dict>, ...]},
              "pairs":               {timestamp: [<pair_id>, ...]},
              "diffs":               {timestamp: {<within-batch comps>}},
            }

        Empty input returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed timeline.
    """
    _validate_timeline_shape(timeline, "generate_structural_report")
    if not timeline:
        return _empty_report()

    structural = analyze_structural_trends(timeline)

    normalised = [(entry[0], entry[1]) for entry in timeline]

    alerts_by_ts: dict = {}
    pairs_by_ts:  dict = {}
    diffs_by_ts:  dict = {}
    for ts, payload in normalised:
        alerts_by_ts[ts] = _alerts_for_batch(payload)
        pairs_by_ts[ts]  = _pairs_for_batch(payload)
        diffs_by_ts[ts]  = _diffs_for_batch(payload)

    headline = _headline_for_structural(structural, len(normalised))

    return {
        "headline":            headline,
        "regime_class":        structural["regime_class"],
        "volatility_variance": float(structural["volatility_variance"]),
        "breakpoints":         structural["breakpoints"],
        "structural_events":   structural["structural_events"],
        "timeline":            structural["timeline"],
        "alerts":              alerts_by_ts,
        "pairs":               pairs_by_ts,
        "diffs":               diffs_by_ts,
    }
