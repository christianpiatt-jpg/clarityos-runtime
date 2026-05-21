"""
el_ins/el_ins_analyzer.py — Unit 74 / v69.

Core EL/INS analyzer. Two modes:

    LLM mode
    --------
    Calls ``model_router.route_request`` with the canonical
    ``skills_export/el_ins/system_prompt.md`` prepended (via a
    one-shot ``[SYSTEM]`` envelope inside the prompt — the router
    doesn't expose a system role today). Parses the model's JSON
    output against ``ElInsResult``. On parse / validation failure
    we retry once, then fall back to the deterministic heuristic.

    Deterministic mode
    ------------------
    Pure-Python heuristic over two keyword vocabularies. Counts hits,
    normalises to a 0-10 score, classifies the ratio, and emits the
    same JSON shape. ``regression_chain`` is minimally populated
    (drivers + precedents left empty). Suitable for offline mode,
    phone runtime, and cheap batch processing.

Pure functions, no I/O at module import beyond reading the system
prompt file once (lazy, cached). Tests reset the cache via
``_reset_prompt_cache``.

Public surface
--------------
    analyze_text(text, *, provider_mode="auto") -> ElInsResult
    analyze_thread(messages, *, provider_mode="auto") -> list[ElInsResult]
    ElInsResult                              (TypedDict matching schema.json)
    PROVIDER_MODES = ("llm", "deterministic", "auto")
    SYSTEM_PROMPT_PATH                       (Path to canonical prompt)
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, TypedDict, Union

logger = logging.getLogger("clarityos.el_ins")

# ---------------------------------------------------------------------------
# Constants + paths
# ---------------------------------------------------------------------------
PROVIDER_MODES: tuple = ("llm", "deterministic", "auto")

# Path to the canonical system prompt in the skills_export bundle.
# Read as plain text — NOT a Python import — so the ARCHITECTURE.md
# no-skills-import boundary is preserved.
_THIS_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = (
    _THIS_DIR.parent / "skills_export" / "el_ins" / "system_prompt.md"
)

# Classification thresholds (per spec §3.2). Tuned so that:
#   ratio > 1.30 → high_el
#   ratio < 0.70 → high_ins
#   else        → balanced
HIGH_EL_THRESHOLD: float = 1.30
HIGH_INS_THRESHOLD: float = 0.70  # ratio strictly below this is high_ins

# Score normalisation cap. Density (hits per 100 tokens) clamped to
# this value, then scaled to 0..10. A "saturated" text scores 10.
_SCORE_DENSITY_CAP: float = 10.0


# ---------------------------------------------------------------------------
# Deterministic vocabularies
#
# These lists are intentionally small + obvious. The heuristic is a
# coarse approximation of the LLM-applied operator — its job is to be
# *directionally correct* on offline paths, not to replicate semantic
# nuance. Maintainers: keep these alphabetised, lowercase, and tight.
# Adding obscure words inflates false positives.
# ---------------------------------------------------------------------------
EMOTIVE_TERMS: frozenset[str] = frozenset({
    # urgency / amplification
    "absolutely", "always", "catastrophic", "certainly", "completely",
    "crisis", "critical", "definitely", "destroy", "devastating",
    "disaster", "doom", "dramatic", "emergency", "essential",
    "everyone", "explosive", "extreme", "fear", "forever",
    "guaranteed", "horror", "horrifying", "imminent", "impossible",
    "incredible", "inevitable", "insane", "miracle", "must",
    "never", "obviously", "outrageous", "panic", "perfect",
    "ruin", "shocking", "stunning", "terrible", "terrify",
    "terrified", "tremendous", "unbelievable", "urgent", "vital",
    # narrative / framing / metaphor
    "beautiful", "brutal", "epic", "fantastic", "gorgeous",
    "heroic", "legendary", "magical", "monumental", "stunning",
    "tragic", "triumphant", "unprecedented", "wondrous",
})

INSTITUTIONAL_TERMS: frozenset[str] = frozenset({
    # legal / regulatory
    "act", "amendment", "appeal", "article", "bill",
    "case", "clause", "code", "complaint", "constitution",
    "contract", "court", "covenant", "decree", "defendant",
    "doctrine", "fiduciary", "filing", "judge", "judgment",
    "jurisdiction", "law", "lawsuit", "legislation", "liability",
    "litigation", "ordinance", "party", "petition", "plaintiff",
    "precedent", "provision", "regulation", "ruling", "section",
    "settlement", "statute", "subpoena", "testimony", "treaty",
    "verdict",
    # data / measurement / structure
    "average", "benchmark", "budget", "calculation", "capacity",
    "census", "coefficient", "constraint", "data", "deadline",
    "deficit", "dependency", "deviation", "duration", "factor",
    "frequency", "gdp", "histogram", "interest", "interval",
    "inventory", "median", "metric", "model", "parameter",
    "percentage", "pipeline", "population", "process", "protocol",
    "quota", "rate", "ratio", "report", "result",
    "sample", "schedule", "specification", "standard", "statistic",
    "survey", "system", "threshold", "throughput", "tolerance",
    "variance", "velocity", "volume",
})


# ---------------------------------------------------------------------------
# TypedDict matching skills_export/el_ins/schema.json
# ---------------------------------------------------------------------------
class _Precedent(TypedDict):
    driver: str
    precedent: str
    principle: str


class _Analysis(TypedDict):
    el_components: list[str]
    ins_components: list[str]
    el_score: float
    ins_score: float
    ratio_classification: str  # high_el | high_ins | balanced


class _RegressionChain(TypedDict):
    projection: Optional[str]
    drivers: list[str]
    precedents: list[_Precedent]
    principle_stack: list[str]
    invariant: Optional[str]


class ElInsResult(TypedDict):
    analysis: _Analysis
    reasoning_mode: str  # stabilize | expand | normal
    regression_chain: _RegressionChain
    stability_notes: Optional[str]


# ---------------------------------------------------------------------------
# System prompt loader (cached)
# ---------------------------------------------------------------------------
_PROMPT_CACHE: Optional[str] = None


def _load_system_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE is not None:
        return _PROMPT_CACHE
    try:
        _PROMPT_CACHE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(
            "el_ins: system_prompt.md not loadable (%s); LLM mode will "
            "fall back to deterministic.", e,
        )
        _PROMPT_CACHE = ""
    return _PROMPT_CACHE


def _reset_prompt_cache() -> None:
    """Test hook — clears the cached system prompt so a fresh read
    happens on the next call. Used by tests that swap the prompt
    file or want to confirm the cache populates."""
    global _PROMPT_CACHE
    _PROMPT_CACHE = None


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")


def _tokenise(text: str) -> list[str]:
    """Lowercase word tokens. Hyphens and apostrophes kept inside a
    token (e.g. ``well-being``, ``can't``). Numbers and punctuation
    stripped."""
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------
def _classify_ratio(el_score: float, ins_score: float) -> str:
    """Return ratio classification per §3.2 thresholds.

    When both scores are zero (no markers detected at all) we return
    ``balanced`` — neither side has expressed dominance.
    """
    if el_score == 0 and ins_score == 0:
        return "balanced"
    # Avoid div-by-zero — if INS is zero but EL isn't, the ratio is
    # effectively infinite → high_el. Symmetric for the other side.
    if ins_score == 0:
        return "high_el"
    if el_score == 0:
        return "high_ins"
    ratio = el_score / ins_score
    if ratio >= HIGH_EL_THRESHOLD:
        return "high_el"
    if ratio < HIGH_INS_THRESHOLD:
        return "high_ins"
    return "balanced"


def _mode_for(classification: str) -> str:
    """Map ratio_classification → reasoning_mode (deterministic)."""
    if classification == "high_el":
        return "stabilize"
    if classification == "high_ins":
        return "expand"
    return "normal"


# ---------------------------------------------------------------------------
# Deterministic analyzer
# ---------------------------------------------------------------------------
def _deterministic_analyze(text: str) -> ElInsResult:
    """Heuristic EL/INS analysis. Pure function — no I/O."""
    tokens = _tokenise(text)
    total = max(1, len(tokens))  # avoid div-by-zero on empty input

    el_hits = [t for t in tokens if t in EMOTIVE_TERMS]
    ins_hits = [t for t in tokens if t in INSTITUTIONAL_TERMS]

    # Density per 100 tokens, capped + scaled to 0..10. A text with
    # 10% emotive markers tops out at score=10.
    el_density = (len(el_hits) / total) * 100.0
    ins_density = (len(ins_hits) / total) * 100.0
    el_score = round(min(_SCORE_DENSITY_CAP, el_density), 2)
    ins_score = round(min(_SCORE_DENSITY_CAP, ins_density), 2)

    classification = _classify_ratio(el_score, ins_score)
    reasoning_mode = _mode_for(classification)

    # Deterministic regression_chain is intentionally minimal — no LLM
    # semantic work happened here. Callers that need a full regression
    # pipeline must use LLM mode.
    regression_chain: _RegressionChain = {
        "projection":      None,
        "drivers":         [],
        "precedents":      [],
        "principle_stack": [],
        "invariant":       None,
    }

    # Preserve token order on the component arrays so the heuristic
    # stays inspectable. Deduplicate while preserving order.
    seen_el: set[str] = set()
    el_components = [t for t in el_hits if not (t in seen_el or seen_el.add(t))]
    seen_ins: set[str] = set()
    ins_components = [t for t in ins_hits if not (t in seen_ins or seen_ins.add(t))]

    return {
        "analysis": {
            "el_components":        el_components,
            "ins_components":       ins_components,
            "el_score":             el_score,
            "ins_score":            ins_score,
            "ratio_classification": classification,
        },
        "reasoning_mode":   reasoning_mode,
        "regression_chain": regression_chain,
        "stability_notes":  (
            f"deterministic heuristic: el={el_score:.2f}, "
            f"ins={ins_score:.2f}, ratio={classification}"
        ),
    }


# ---------------------------------------------------------------------------
# LLM analyzer
# ---------------------------------------------------------------------------
def _coerce_llm_output(raw: Union[str, dict]) -> Optional[ElInsResult]:
    """Try to parse a model response into the ElInsResult shape.

    Accepts either a dict (already JSON) or a string that we attempt
    to ``json.loads``. Returns None on any failure — caller decides
    whether to retry or fall back.
    """
    if isinstance(raw, dict):
        body = raw
    elif isinstance(raw, str):
        # Some models wrap JSON in code fences. Strip a single fence
        # if present.
        s = raw.strip()
        if s.startswith("```"):
            fence_end = s.find("\n")
            if fence_end > 0:
                s = s[fence_end + 1:]
            if s.endswith("```"):
                s = s[:-3]
        try:
            body = json.loads(s)
        except (ValueError, TypeError):
            return None
    else:
        return None

    if not isinstance(body, dict):
        return None
    analysis = body.get("analysis")
    if not isinstance(analysis, dict):
        return None
    cls = analysis.get("ratio_classification")
    if cls not in ("high_el", "high_ins", "balanced"):
        return None
    mode = body.get("reasoning_mode")
    if mode not in ("stabilize", "expand", "normal"):
        return None
    # Defensive normalisation: fill any missing top-level keys with
    # sensible defaults so the result is schema-valid even if the
    # model omitted optional fields.
    rc = body.get("regression_chain") or {}
    if not isinstance(rc, dict):
        rc = {}
    coerced: ElInsResult = {
        "analysis": {
            "el_components":        list(analysis.get("el_components") or []),
            "ins_components":       list(analysis.get("ins_components") or []),
            "el_score":             float(analysis.get("el_score") or 0.0),
            "ins_score":            float(analysis.get("ins_score") or 0.0),
            "ratio_classification": cls,
        },
        "reasoning_mode":   mode,
        "regression_chain": {
            "projection":      rc.get("projection") if isinstance(rc.get("projection"), str) else None,
            "drivers":         [str(x) for x in (rc.get("drivers") or [])],
            "precedents":      [_coerce_precedent(p) for p in (rc.get("precedents") or []) if isinstance(p, dict)],
            "principle_stack": [str(x) for x in (rc.get("principle_stack") or [])],
            "invariant":       rc.get("invariant") if isinstance(rc.get("invariant"), str) else None,
        },
        "stability_notes":  body.get("stability_notes") if isinstance(body.get("stability_notes"), str) else None,
    }
    return coerced


def _coerce_precedent(p: dict) -> _Precedent:
    return {
        "driver":    str(p.get("driver", "")),
        "precedent": str(p.get("precedent", "")),
        "principle": str(p.get("principle", "")),
    }


def _llm_analyze(text: str) -> Optional[ElInsResult]:
    """Try LLM mode. Returns None on any failure (caller falls back).

    Imports model_router lazily — keeps el_ins importable in test
    contexts that monkeypatch the router.
    """
    prompt_body = _load_system_prompt()
    if not prompt_body:
        return None
    # The router doesn't expose a "system role"; envelope the prompt
    # so the model sees the directive clearly before the user text.
    prompt = (
        "[SYSTEM]\n"
        f"{prompt_body}\n"
        "[END SYSTEM]\n\n"
        "Analyze the following text and emit a SINGLE JSON object that "
        "matches the EL/INS schema. Do not include any prose outside "
        "the JSON object. Begin output with '{' and end with '}'.\n\n"
        "[TEXT]\n"
        f"{text}\n"
        "[END TEXT]"
    )
    try:
        import model_router  # lazy
        # Use the deterministic reasoning default; this analysis is
        # tone-sensitive and benefits from claude-3.7. The task key
        # falls back to TASK_DEFAULTS so we don't burn through user
        # preferred_model selection.
        result = model_router.route_request(
            model_router.AUTO,
            prompt,
            temperature=0.0,
            max_tokens=2048,
        )
    except Exception as e:  # pragma: no cover (live model only)
        logger.debug("el_ins: llm call raised; falling back. err=%s", e)
        return None
    if not isinstance(result, dict):
        return None
    text_out = result.get("text") or ""
    return _coerce_llm_output(text_out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze_text(
    text: str,
    *,
    provider_mode: Literal["llm", "deterministic", "auto"] = "auto",
) -> ElInsResult:
    """Analyze a single text. Returns a fully-shaped ``ElInsResult``.

    ``provider_mode``:
        - ``"llm"``           — use LLM only; if the call fails or the
                                 output can't be parsed, fall back to
                                 deterministic anyway (we never raise).
        - ``"deterministic"`` — heuristic only, no LLM call.
        - ``"auto"``          — try LLM first, fall back to heuristic
                                 (this is the production default).

    Empty / whitespace-only input returns a deterministic ``balanced``
    result with zero scores.
    """
    if provider_mode not in PROVIDER_MODES:
        raise ValueError(
            f"provider_mode must be one of {PROVIDER_MODES}, got "
            f"{provider_mode!r}"
        )
    text = (text or "").strip()
    if not text:
        return _deterministic_analyze("")

    if provider_mode == "deterministic":
        return _deterministic_analyze(text)

    # llm or auto
    llm_result = _llm_analyze(text)
    if llm_result is not None:
        return llm_result
    return _deterministic_analyze(text)


def analyze_thread(
    messages: Iterable[str],
    *,
    provider_mode: Literal["llm", "deterministic", "auto"] = "auto",
) -> list[ElInsResult]:
    """Batch analysis. One ``ElInsResult`` per input message, preserving
    order. Empty / whitespace messages still produce a result (so the
    list length matches the input length)."""
    return [
        analyze_text(m, provider_mode=provider_mode)
        for m in messages
    ]
