"""
regression_trace.py — deterministic causal regression for #regression (A24).

Pure, side-effect-free backward causal trace of text — the backward half of
Double Regression. It produces:

    events           — event-like sentences, in text (assumed-forward) order
    Causal Chain     — those events reversed (outcome -> ... -> origin)
    turning_points   — events carrying a causal/pivot marker
    drivers          — events naming a structural driver
    emergence        — the root-cause event (explicit origin marker, else the
                       earliest event) + a content-free "kind" label

HONESTY NOTE (same posture as primitives_extract / cite_mode): this is a
deterministic HEURISTIC scaffold, not causal inference. The runtime has no NLP
dependency and forbids adding one, so "temporal ordering" is the heuristic
"text order is roughly forward in time, so the backward chain is its reverse,"
and causality is keyword-detected. It is lossy and approximate by design.

Telemetry hygiene: metadata exposes ``emergence`` as a content-free KIND label
("marked" | "earliest" | "none"), never the root-cause text. The actual
root-cause text appears only in the rendered "Primitive Emergence" section, so
when the engine is wired (A28) directive metadata never carries reply content.

Determinism: outputs are ordered by text appearance; marker checks are boolean
``any(...)`` over fixed tuples (never set-iteration).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_CAP = 30
_CLAUSE_MAXLEN = 200

_CAUSAL = (
    "because", "therefore", "thus", "hence", "due to", "led to", "leads to",
    "leading to", "resulted in", "results in", "caused", "causes", "triggered",
    "triggers", "so that", "as a result", "gave rise to", "brought about",
)
_PIVOT = (
    "then", "suddenly", "finally", "but", "however", "until", "once",
    "subsequently", "eventually", "afterward", "afterwards", "next",
)
_TURNING = _CAUSAL + _PIVOT
_DRIVERS = (
    "constraint", "constraints", "pressure", "demand", "incentive",
    "incentives", "goal", "goals", "motivation", "motive", "force", "forces",
    "factor", "factors", "driver", "drivers", "structural", "budget", "cost",
    "competition", "regulation", "market",
)
_ORIGIN = (
    "root cause", "originated", "origin", "stems from", "stem from", "began",
    "begin", "started", "starts", "initially", "at first", "arose", "emerged",
    "emerges", "sprang from", "traces back", "goes back to",
)


def _empty() -> Dict:
    return {"events": [], "turning_points": [], "drivers": [],
            "emergence": None, "emergence_kind": "none"}


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _trim(s: str) -> str:
    s = s.strip()
    return s if len(s) <= _CLAUSE_MAXLEN else s[:_CLAUSE_MAXLEN].rstrip() + "…"


def _is_event(s: str) -> bool:
    return len(s.split()) >= 2


def _has_any(s: str, markers) -> bool:
    ls = s.lower()
    return any(m in ls for m in markers)


def _emergence(events: List[str]) -> Tuple[Optional[str], str]:
    for e in events:
        if _has_any(e, _ORIGIN):
            return e, "marked"
    if events:
        return events[0], "earliest"
    return None, "none"


def regress(text: str) -> Dict:
    """Backward causal regression of ``text``. Non-str/empty → empty trace."""
    if not isinstance(text, str) or not text.strip():
        return _empty()
    events = [_trim(s) for s in _sentences(text) if _is_event(s)][:_CAP]
    turning = [e for e in events if _has_any(e, _TURNING)][:_CAP]
    drivers = [e for e in events if _has_any(e, _DRIVERS)][:_CAP]
    emergence, kind = _emergence(events)
    return {
        "events": events,
        "turning_points": turning,
        "drivers": drivers,
        "emergence": emergence,
        "emergence_kind": kind,
    }


def build_metadata(r: Dict) -> Dict:
    return {
        "status": "regressed",
        "length": len(r["events"]),
        "turning_points": len(r["turning_points"]),
        "emergence": r["emergence_kind"],   # content-free label
    }


def _bullets(items: List[str]) -> List[str]:
    return [f"- {it}" for it in items] if items else ["- _(none detected)_"]


def format_regression(r: Dict) -> str:
    """Render the canonical Markdown regression (stable section order)."""
    lines: List[str] = ["# Regression Analysis", "", "## Causal Chain (Backward)"]
    chain = list(reversed(r["events"]))
    if chain:
        lines += [f"{i}. {e}" for i, e in enumerate(chain, 1)]
    else:
        lines.append("_(none detected)_")
    lines.append("")
    lines.append("## Turning Points"); lines += _bullets(r["turning_points"]); lines.append("")
    lines.append("## Structural Drivers"); lines += _bullets(r["drivers"]); lines.append("")
    lines.append("## Primitive Emergence")
    lines += _bullets([r["emergence"]] if r["emergence"] else [])
    return "\n".join(lines)
