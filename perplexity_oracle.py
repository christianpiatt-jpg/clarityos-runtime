"""
v35 — Perplexity Oracle (External Signal Object).

Deterministic, pure provider that returns an ESO (External Signal Object)
for a given regional basin. The runtime never actually hits Perplexity in
this revision — the function is fully synthetic + same-input-same-output
so tests + offline UI development work without network. The real Perplexity
integration is gated behind ``CLARITYOS_PERPLEXITY_API_KEY`` and is a
no-op stub in this module; flipping the flag will only matter once the
remote provider is wired in.

ESO shape (the contract regional_elins consumes):

    {
        "region_code": str,
        "signals": [
            {"key": <primitive_key>, "intensity": float, "weight": float,
             "source": str, "anchor": Optional[str]},
            ...
        ],
        "anchors": [str, ...],
        "domain_bias": {<domain_key>: float, ...},
        "fetched_at": float,
        "version": str,
        "mock": bool,
    }

Public API:

    fetch_basin_signals(region_code, *, user=None, mode="auto") -> dict | None
    is_eso_enabled(user_doc) -> bool
    REGION_FIXTURES                # static per-region ESO templates
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Optional

logger = logging.getLogger("clarityos.perplexity_oracle")


SUPPORTED_REGIONS: tuple = ("US", "EU", "MEA", "APAC", "Markets", "Tech")
ORACLE_VERSION: str = "perplexity_oracle.v41.1"

# v41 — real HTTP client config (guarded behind the API-key env var).
_DEFAULT_PERPLEXITY_ENDPOINT: str = "https://api.perplexity.ai/chat/completions"
_DEFAULT_PERPLEXITY_MODEL: str = "sonar-medium-online"
_PERPLEXITY_TIMEOUT_S: float = 10.0

# Module state for observability — last error info gets surfaced via
# the kernel-status endpoint and reset on every successful call.
_last_error_ts: Optional[float] = None
_last_error_msg: Optional[str] = None
_warned_missing_key: bool = False

# Sanitisation knobs — strings longer than this are truncated; field
# names that look like article bodies / HTML are dropped wholesale.
_MAX_STR_LEN: int = 2000
_FORBIDDEN_BODY_KEYS: frozenset = frozenset({
    "body", "html", "raw_body", "article_body", "content", "html_content",
    "full_text", "raw_html",
})
_HTML_TAG_RE: re.Pattern = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Static per-region ESO fixtures.
# These represent what a real Perplexity call would distill into structured
# primitives + anchors. Every value is constant — same call → same return —
# so downstream forecasts stay deterministic.
# ---------------------------------------------------------------------------
REGION_FIXTURES: dict[str, dict] = {
    "US": {
        "signals": [
            {"key": "pressure",      "intensity": 0.62, "weight": 1.00,
             "source": "policy_brief", "anchor": "Federal Reserve rate path"},
            {"key": "contradiction", "intensity": 0.45, "weight": 0.80,
             "source": "headline",     "anchor": "Senate filibuster procedural vote"},
            {"key": "tension",       "intensity": 0.50, "weight": 0.85,
             "source": "wire_summary", "anchor": "Border policy negotiations"},
        ],
        "anchors": [
            "Federal Reserve rate path",
            "Senate filibuster procedural vote",
            "Border policy negotiations",
        ],
        "domain_bias": {"economic": 0.30, "geopolitical": 0.25, "legal": 0.20},
    },
    "EU": {
        "signals": [
            {"key": "pressure",  "intensity": 0.55, "weight": 0.90,
             "source": "policy_brief", "anchor": "ECB inflation guidance"},
            {"key": "tension",   "intensity": 0.45, "weight": 0.80,
             "source": "wire_summary", "anchor": "Brussels migration package"},
            {"key": "alignment", "intensity": 0.40, "weight": 0.70,
             "source": "headline",     "anchor": "EU defense bloc coordination"},
        ],
        "anchors": [
            "ECB inflation guidance",
            "Brussels migration package",
            "EU defense bloc coordination",
        ],
        "domain_bias": {"economic": 0.25, "geopolitical": 0.30, "institutional": 0.20},
    },
    "MEA": {
        "signals": [
            {"key": "pressure",      "intensity": 0.75, "weight": 1.00,
             "source": "wire_summary", "anchor": "Gulf shipping disruption"},
            {"key": "tension",       "intensity": 0.70, "weight": 0.95,
             "source": "wire_summary", "anchor": "Iran proxy escalation"},
            {"key": "drift",         "intensity": 0.50, "weight": 0.80,
             "source": "policy_brief", "anchor": "OPEC supply posture"},
            {"key": "contradiction", "intensity": 0.40, "weight": 0.65,
             "source": "headline",     "anchor": "Regional alliance signaling"},
        ],
        "anchors": [
            "Gulf shipping disruption",
            "Iran proxy escalation",
            "OPEC supply posture",
            "Regional alliance signaling",
        ],
        "domain_bias": {"geopolitical": 0.45, "economic": 0.20, "ecological": 0.10},
    },
    "APAC": {
        "signals": [
            {"key": "drift",     "intensity": 0.55, "weight": 0.85,
             "source": "policy_brief", "anchor": "Cross-strait military rebalancing"},
            {"key": "tension",   "intensity": 0.50, "weight": 0.85,
             "source": "headline",     "anchor": "South China Sea claims"},
            {"key": "alignment", "intensity": 0.45, "weight": 0.75,
             "source": "wire_summary", "anchor": "AUKUS technology deepening"},
        ],
        "anchors": [
            "Cross-strait military rebalancing",
            "South China Sea claims",
            "AUKUS technology deepening",
        ],
        "domain_bias": {"geopolitical": 0.35, "technological": 0.20, "economic": 0.15},
    },
    "Markets": {
        "signals": [
            {"key": "pressure",      "intensity": 0.65, "weight": 1.00,
             "source": "wire_summary", "anchor": "Equity volatility regime"},
            {"key": "drift",         "intensity": 0.45, "weight": 0.80,
             "source": "policy_brief", "anchor": "Yield curve repricing"},
            {"key": "contradiction", "intensity": 0.40, "weight": 0.65,
             "source": "headline",     "anchor": "Risk-on / risk-off mismatch"},
        ],
        "anchors": [
            "Equity volatility regime",
            "Yield curve repricing",
            "Risk-on / risk-off mismatch",
        ],
        "domain_bias": {"economic": 0.50, "geopolitical": 0.10},
    },
    "Tech": {
        "signals": [
            {"key": "drift",     "intensity": 0.60, "weight": 0.90,
             "source": "policy_brief", "anchor": "Frontier model release cadence"},
            {"key": "alignment", "intensity": 0.45, "weight": 0.75,
             "source": "wire_summary", "anchor": "Open-weight ecosystem coalescing"},
            {"key": "tension",   "intensity": 0.40, "weight": 0.70,
             "source": "headline",     "anchor": "Compute supply concentration"},
        ],
        "anchors": [
            "Frontier model release cadence",
            "Open-weight ecosystem coalescing",
            "Compute supply concentration",
        ],
        "domain_bias": {"technological": 0.45, "economic": 0.20},
    },
}


def is_eso_enabled(user_doc: Optional[dict]) -> bool:
    """Return True iff the user has opted into the cloud_perplexity signal
    mode. Anything else (None, "off", missing key) returns False."""
    if not isinstance(user_doc, dict):
        return False
    return str(user_doc.get("external_signal_mode") or "").strip() == "cloud_perplexity"


def _deterministic_seed(region_code: str) -> int:
    h = hashlib.sha256(region_code.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _cloud_provider_active() -> bool:
    """Real Perplexity is opt-in via env. The default is the pure-mock path."""
    return bool((os.environ.get("CLARITYOS_PERPLEXITY_API_KEY") or "").strip())


def fetch_basin_signals(
    region_code: str,
    *,
    user: Optional[str] = None,
    mode: str = "auto",
) -> Optional[dict]:
    """Return the ESO for a region.

    Modes:
        "auto"   — call the real Perplexity API when ``CLARITYOS_PERPLEXITY_API_KEY``
                   is set; otherwise return the deterministic mock fixture.
        "mock"   — always return the static fixture.
        "off"    — always return None.

    Real-mode failures (timeouts, non-2xx, JSON errors) propagate to
    the caller as exceptions; the kernel's ``_maybe_fetch_eso`` wraps
    them so a single failed fetch never breaks an ELINS run.
    """
    if mode == "off":
        return None
    if region_code not in REGION_FIXTURES:
        raise ValueError(f"unknown region_code {region_code!r}")

    # Decide path. In "mock" mode we never touch the network. In "auto"
    # mode we follow the env-var gate.
    if mode == "mock" or not _cloud_provider_active():
        if not _cloud_provider_active():
            _maybe_warn_missing_key()
        return _build_mock_eso(region_code, user=user)

    # Live path — call Perplexity.
    query = _query_for_region(region_code)
    raw = _call_perplexity(query)                   # may raise
    eso = _normalize_to_eso(raw, region_code=region_code)
    eso["user"] = user
    eso["source"] = "perplexity"
    eso["mock"] = False
    eso["version"] = ORACLE_VERSION
    eso = sanitize_eso(eso)
    _clear_error()
    return eso


# ---------------------------------------------------------------------------
# Mock-mode ESO builder
# ---------------------------------------------------------------------------
def _build_mock_eso(region_code: str, *, user: Optional[str]) -> dict:
    fixture = REGION_FIXTURES[region_code]
    anchors = list(fixture["anchors"])
    signals = [dict(s) for s in fixture["signals"]]
    # v41 — surface the additional ESO-shape fields alongside the
    # legacy v35 fields. Mock mode synthesises them deterministically
    # so tests stay reproducible.
    facts = [str(a) for a in anchors]
    entities = [str(s.get("anchor") or s.get("key") or "") for s in signals if s.get("anchor")]
    timestamps = [_deterministic_fetched_at(region_code)] * max(1, len(facts))
    sources: list[str] = []  # mock has no URL list
    return {
        "region_code": region_code,
        "signals": signals,
        "anchors": anchors,
        "domain_bias": dict(fixture["domain_bias"]),
        "fetched_at": _deterministic_fetched_at(region_code),
        "version": ORACLE_VERSION,
        "mock": True,
        "source": "mock",
        "user": user,
        # v41 augmented shape
        "sources": sources,
        "facts": facts,
        "entities": entities,
        "timestamps": timestamps,
        "confidence": 0.7,
    }


# ---------------------------------------------------------------------------
# Real Perplexity HTTP client
# ---------------------------------------------------------------------------
def _query_for_region(region_code: str) -> str:
    """Stable structured prompt the live API gets for a basin. Designed
    to elicit a JSON answer with facts/entities/sources/confidence."""
    fixture = REGION_FIXTURES.get(region_code) or {}
    seed = ", ".join(fixture.get("anchors") or []) or region_code
    return (
        f"Return a compact JSON object describing the most pressing "
        f"current dynamics in the {region_code} basin (seed context: "
        f"{seed}). Required keys: facts (list of <=200-char strings), "
        f"entities (list of named entities), sources (list of URLs), "
        f"confidence (float 0-1). No commentary outside the JSON."
    )


def _call_perplexity(query: str) -> dict:
    """Issue one POST against the Perplexity chat-completions endpoint.

    Raises ``RuntimeError`` when the API key is unset (callers should
    pre-check via ``_cloud_provider_active``). Wraps urllib errors in
    ``RuntimeError`` for a uniform exception type the kernel can
    handle.
    """
    api_key = (os.environ.get("CLARITYOS_PERPLEXITY_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("CLARITYOS_PERPLEXITY_API_KEY not set")
    endpoint = (
        os.environ.get("CLARITYOS_PERPLEXITY_ENDPOINT")
        or _DEFAULT_PERPLEXITY_ENDPOINT
    )
    body = {
        "model": _DEFAULT_PERPLEXITY_MODEL,
        "messages": [
            {"role": "system",
             "content": "Return only a single JSON object — no markdown, no commentary."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_PERPLEXITY_TIMEOUT_S) as resp:
            payload = resp.read().decode("utf-8")
        return json.loads(payload)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        _record_error(f"http: {e}")
        raise RuntimeError(f"perplexity HTTP error: {e}") from e
    except (json.JSONDecodeError, ValueError) as e:
        _record_error(f"json: {e}")
        raise RuntimeError(f"perplexity JSON error: {e}") from e


def _normalize_to_eso(raw: dict, *, region_code: str) -> dict:
    """Convert a raw Perplexity chat-completion JSON into the ESO shape.

    Tolerates a variety of response shapes: the model may return the
    JSON directly in ``choices[0].message.content`` (Perplexity's
    default), wrap it in a code fence, or — pathologically — embed it
    inside a longer string. The function pulls out the largest braced
    JSON object it can find and falls back to an empty ESO when no
    JSON is recoverable.
    """
    if not isinstance(raw, dict):
        return _empty_eso(region_code)
    content = ""
    try:
        choices = raw.get("choices") or []
        if choices and isinstance(choices[0], dict):
            content = (choices[0].get("message") or {}).get("content") or ""
    except Exception:  # pragma: no cover (defensive)
        content = ""
    parsed_raw = _extract_json(content) if content else None
    parseable = isinstance(parsed_raw, dict)
    parsed = parsed_raw if parseable else {}

    facts = _coerce_str_list(parsed.get("facts"))
    entities = _coerce_str_list(parsed.get("entities"))
    sources = _coerce_str_list(parsed.get("sources"))
    timestamps_raw = parsed.get("timestamps") or []
    timestamps: list[float] = []
    if isinstance(timestamps_raw, list):
        for t in timestamps_raw:
            try:
                timestamps.append(float(t))
            except (TypeError, ValueError):
                continue
    confidence_raw = parsed.get("confidence")
    if confidence_raw is None:
        # Parse succeeded but no confidence reported → mid value.
        # Parse failed entirely → 0.0 (no data to be confident about).
        confidence = 0.5 if parseable else 0.0
    else:
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.5

    # Synthesise legacy v35 fields from the new content so downstream
    # ELINS code (which reads signals/anchors/domain_bias) keeps
    # working. We weight the first 6 facts at 0.6 each as a default.
    legacy_anchors = facts[:6] or entities[:6]
    legacy_signals: list[dict] = []
    for i, anchor in enumerate(legacy_anchors):
        legacy_signals.append({
            "key": _PRIMITIVE_BY_INDEX[i % len(_PRIMITIVE_BY_INDEX)],
            "intensity": round(0.4 + 0.1 * (1.0 / max(1, i + 1)), 4),
            "weight": 1.0,
            "source": "perplexity",
            "anchor": anchor,
        })
    fixture_bias = (REGION_FIXTURES.get(region_code) or {}).get("domain_bias") or {}

    return {
        "region_code": region_code,
        "signals": legacy_signals,
        "anchors": list(legacy_anchors),
        "domain_bias": dict(fixture_bias),
        "fetched_at": time.time(),
        "version": ORACLE_VERSION,
        # v41 augmented shape:
        "sources": sources,
        "facts": facts,
        "entities": entities,
        "timestamps": timestamps,
        "confidence": max(0.0, min(1.0, confidence)),
    }


def _empty_eso(region_code: str) -> dict:
    """Empty-but-valid ESO used when normalisation finds nothing
    parseable."""
    return {
        "region_code": region_code,
        "signals": [],
        "anchors": [],
        "domain_bias": {},
        "fetched_at": time.time(),
        "version": ORACLE_VERSION,
        "sources": [], "facts": [], "entities": [], "timestamps": [],
        "confidence": 0.0,
    }


# Stable primitive cycle for legacy_signals when we synthesise from
# entity lists (v41 fallback). Keeps determinism for fixed inputs.
_PRIMITIVE_BY_INDEX: tuple = (
    "pressure", "tension", "drift", "contradiction", "trust", "alignment",
)


def _extract_json(content: str) -> Any:
    """Best-effort: find the largest balanced ``{...}`` substring and
    json.loads it. Tolerates code fences and prose. Returns None when
    no JSON is recoverable."""
    if not isinstance(content, str) or not content.strip():
        return None
    s = content.strip()
    # Strip markdown code fences.
    if s.startswith("```"):
        s = s.strip("`")
        # Drop optional language tag on the first line.
        if "\n" in s:
            s = s.split("\n", 1)[1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Locate the outermost balanced braces.
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = s[start:end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _coerce_str_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for item in v:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif item is not None:
            s = str(item).strip()
            if s:
                out.append(s)
    return out


# ---------------------------------------------------------------------------
# sanitize_eso
# ---------------------------------------------------------------------------
def sanitize_eso(eso: Optional[dict]) -> Optional[dict]:
    """Return a defensive copy with HTML stripped, long strings
    truncated to ``_MAX_STR_LEN``, and known body / html keys
    dropped. Used by the kernel before any ESO is handed to ELINS or
    #G."""
    if not isinstance(eso, dict):
        return None
    return _sanitize_value(eso)


def _strip_html(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return _HTML_TAG_RE.sub("", text)


def _sanitize_value(v: Any) -> Any:
    if isinstance(v, str):
        cleaned = _strip_html(v)
        if len(cleaned) > _MAX_STR_LEN:
            cleaned = cleaned[:_MAX_STR_LEN]
        return cleaned
    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k, vv in v.items():
            if not isinstance(k, str):
                continue
            if k.lower() in _FORBIDDEN_BODY_KEYS:
                continue
            out[k] = _sanitize_value(vv)
        return out
    if isinstance(v, list):
        return [_sanitize_value(x) for x in v]
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    s = str(v)
    return s if len(s) <= _MAX_STR_LEN else s[:_MAX_STR_LEN]


# ---------------------------------------------------------------------------
# Error tracking + provider-active warning
# ---------------------------------------------------------------------------
def _record_error(msg: str) -> None:
    global _last_error_ts, _last_error_msg
    _last_error_ts = time.time()
    _last_error_msg = (msg or "")[:200]
    logger.warning("perplexity oracle error: %s", _last_error_msg)


def _clear_error() -> None:
    global _last_error_ts, _last_error_msg
    _last_error_ts = None
    _last_error_msg = None


def get_last_error() -> dict:
    return {"ts": _last_error_ts, "message": _last_error_msg}


def _maybe_warn_missing_key() -> None:
    """Log a one-shot warning the first time a caller asks for an ESO
    while the API key is unset. Subsequent calls stay quiet so we don't
    spam logs at scheduler tick rate."""
    global _warned_missing_key
    if _warned_missing_key:
        return
    _warned_missing_key = True
    logger.warning(
        "CLARITYOS_PERPLEXITY_API_KEY not set — falling back to mock ESO. "
        "Set the env var to enable live Perplexity calls.",
    )


def provider_status() -> dict:
    """Return the public ``perplexity`` block embedded in the kernel
    status endpoint (v41)."""
    configured = _cloud_provider_active()
    return {
        "configured": configured,
        "mode": "live" if configured else "mock",
        "endpoint": (
            os.environ.get("CLARITYOS_PERPLEXITY_ENDPOINT")
            or _DEFAULT_PERPLEXITY_ENDPOINT
        ),
        "last_error_ts": _last_error_ts,
        "last_error_message": _last_error_msg,
    }


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    global _last_error_ts, _last_error_msg, _warned_missing_key
    _last_error_ts = None
    _last_error_msg = None
    _warned_missing_key = False


def _deterministic_fetched_at(region_code: str) -> float:
    """A deterministic float per region. Real implementations will use
    time.time(); using a stable value lets tests pin output exactly."""
    seed = _deterministic_seed(region_code)
    # Pick a stable epoch in the past so the value is recognisable as a
    # real-looking timestamp (useful in UI fixtures).
    return float(1_700_000_000 + (seed % 100_000))
