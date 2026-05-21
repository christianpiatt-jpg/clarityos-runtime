"""
email_ep_dash.py — EMAIL EP DASH (Phase 2 Unit 2).

Manual paste / forward channel for email intelligence. The operator
pastes a raw email blob; this module parses it into a canonical
packet, derives lexical EP signals (NO LLM calls), wraps it in an
envelope, writes the envelope to the ingestion bus, and persists a
JSON archive copy to the library directory.

EMAIL-ONLY. No news signals, no personal ELINS signals — the spec is
explicit on isolation. DAILY PERSONAL ELINS (Phase 2 Unit 3) consumes
these envelopes downstream into the MESO section.

DESIGN COMMITMENTS:
    * Mirrors personal_news_basin.py exactly in shape:
        - Same 7-function public surface
        - Same env-var-overridable archive directory
        - Same ingestion_bus.write_packet sink
        - Same JSON file naming (YYYY-MM-DD_HHMM.json)
        - Same graceful-degradation discipline (no raise on garbage)
    * Pure deterministic classification. EP flags / importance /
      commitment + request markers are all regex/keyword-driven, no
      LLM calls. Makes the path free, fast, and reproducible.
    * No MIME parsing. The spec accepts simple ``From:``/``To:``/
      ``Subject:``/``Date:`` headers + blank-line-delimited body.
      Folded continuation lines (RFC 5322 §2.2.3) are unfolded.
    * 1 item per call. The paste/forward channel is single-email by
      definition; the envelope's ``items`` list always has 0 or 1
      entry. Multi-email batching is a future surface concern.

CONFIG:
    Archive dir:  ClarityOS_Library/email_ep_dash
        Files named YYYY-MM-DD_HHMM.json.
        Override with CLARITYOS_EMAIL_EP_DASH_DIR.

PUBLIC API (per spec):
    parse_email_blob(raw)                  -> dict
    normalize_email(email, user_id)        -> dict
    build_email_dash_envelope(items, uid)  -> dict
    write_to_ingestion_bus(envelope)       -> str   # packet_id
    write_to_library(envelope)             -> str   # file path
    run_email_ep_dash(raw, user_id)        -> dict  # entrypoint
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("clarityos.email_ep_dash")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LIBRARY_DIR: str = "ClarityOS_Library/email_ep_dash"
ENVELOPE_TYPE:       str = "email_ep_dash"

# Canonical packet key set. Documented for downstream consumers.
PACKET_KEYS: tuple = (
    "from",
    "to",
    "cc",
    "subject",
    "date",
    "body",
    "thread_key",
    "importance",
    "has_deadline",
    "commitment_markers",
    "request_markers",
    "ep_flags",
)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def _resolve_library_dir() -> Path:
    """Resolve the email-dash archive directory.

    Honors ``CLARITYOS_EMAIL_EP_DASH_DIR``; falls back to
    ``DEFAULT_LIBRARY_DIR`` relative to the current working directory.
    """
    override = (os.environ.get("CLARITYOS_EMAIL_EP_DASH_DIR") or "").strip()
    return Path(override) if override else Path(DEFAULT_LIBRARY_DIR)


# ---------------------------------------------------------------------------
# 1. parse_email_blob
# ---------------------------------------------------------------------------
def _split_addresses(value: str) -> list[str]:
    """Split a comma-separated address list, stripping each part.

    Robust against trailing/leading whitespace and empty segments.
    Does NOT attempt to validate addresses — the paste/forward channel
    accepts whatever the operator gives us.
    """
    if not isinstance(value, str) or not value.strip():
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


def parse_email_blob(raw: str) -> dict:
    """Parse a raw email blob into header dict + body string.

    Recognised headers (case-insensitive): From, To, Cc, Subject, Date.
    Multi-recipient To/Cc are split on comma. Folded continuation
    lines (RFC 5322 §2.2.3 — lines starting with SP/TAB) are joined
    to the preceding header. Body is everything after the first blank
    line.

    Always returns a dict — never raises. Missing fields default to
    "" / [] / None as appropriate.
    """
    if not isinstance(raw, str):
        return {
            "from":    "",
            "to":      [],
            "cc":      [],
            "subject": "",
            "date":    None,
            "body":    "",
        }

    # Normalise line endings + split.
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Skip leading blank lines.
    while lines and not lines[0].strip():
        lines.pop(0)

    # Find blank line separating headers from body.
    header_lines: list[str] = []
    body_start = len(lines)
    for i, line in enumerate(lines):
        if not line.strip():
            body_start = i + 1
            break
        header_lines.append(line)

    body = "\n".join(lines[body_start:]).strip()

    # Unfold continuation lines: any line starting with whitespace
    # is appended to the preceding header value.
    unfolded: list[str] = []
    for line in header_lines:
        if line and line[0] in (" ", "\t") and unfolded:
            unfolded[-1] = unfolded[-1] + " " + line.strip()
        else:
            unfolded.append(line)

    # Parse header lines into a case-insensitive dict.
    headers: dict[str, str] = {}
    for line in unfolded:
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        key = name.strip().lower()
        if not key:
            continue
        # First occurrence wins (matches RFC 5322 spirit).
        if key not in headers:
            headers[key] = value.strip()

    return {
        "from":    headers.get("from", ""),
        "to":      _split_addresses(headers.get("to", "")),
        "cc":      _split_addresses(headers.get("cc", "")),
        "subject": headers.get("subject", ""),
        "date":    headers.get("date") or None,
        "body":    body,
    }


# ---------------------------------------------------------------------------
# 2. normalize_email — derives all signals deterministically
# ---------------------------------------------------------------------------

# Importance lexical markers. HIGH wins over MEDIUM wins over LOW
# (default). Operator can tune the lists without retraining anything.
_IMPORTANCE_HIGH: tuple = (
    "urgent", "asap", "immediately", "critical", "emergency",
    "important", "time-sensitive", "time sensitive", "high priority",
)
_IMPORTANCE_MEDIUM: tuple = (
    "please review", "follow up", "follow-up", "deadline",
    "respond", "needed", "by tomorrow", "by friday",
    "action required", "kindly review", "approval needed",
)


def _classify_importance(subject: str, body: str) -> str:
    """Lexical importance classifier. HIGH | MEDIUM | LOW.

    Subject markers count the same as body markers. First bucket to
    match wins (HIGH checked before MEDIUM).
    """
    text = f"{subject}\n{body}".lower()
    if any(kw in text for kw in _IMPORTANCE_HIGH):
        return "HIGH"
    if any(kw in text for kw in _IMPORTANCE_MEDIUM):
        return "MEDIUM"
    return "LOW"


# Deadline detection. Matches:
#   * "by <day-of-week>", "by tomorrow", "by today", "by next week",
#   * "by end of day/week/month",
#   * "by <numeric date>" (1/15, 1-15-26, etc.)
#   * "by <month name>",
#   * "deadline" anywhere,
#   * "due on/by/tomorrow/<day-of-week>",
#   * "no later than".
_DEADLINE_RE = re.compile(
    r"(?:"
    r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|tomorrow|today|next\s+week|end\s+of\s+(?:day|week|month)"
    r"|\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?"
    r"|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?"
    r"|nov(?:ember)?|dec(?:ember)?)"
    r"|\bdeadline\b"
    r"|\bdue\s+(?:on|by|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|\bno\s+later\s+than\b"
    r")",
    re.IGNORECASE,
)


def _has_deadline(subject: str, body: str) -> bool:
    text = f"{subject}\n{body}"
    return bool(_DEADLINE_RE.search(text))


# Commitment / request marker patterns. Stored as regex strings so we
# can find phrase substrings (NOT word-boundary alone) and dedupe the
# matched phrases in the result.
_COMMITMENT_PATTERNS: tuple = (
    r"\bi\s+will\b",
    r"\bi'?ll\b",
    r"\bwe\s+will\b",
    r"\bwe'?ll\b",
    r"\bi\s+(?:can|could)\s+(?:do|handle|take\s+care\s+of|manage)\b",
    r"\bi\s+promise\b",
    r"\bi\s+commit\b",
    r"\bi\s+agree\s+to\b",
    r"\bi\s+will\s+(?:send|deliver|review|complete)\b",
    r"\bgoing\s+to\b",
)

_REQUEST_PATTERNS: tuple = (
    r"\bcan\s+you\b",
    r"\bcould\s+you\b",
    r"\bwould\s+you\b",
    r"\bplease\b",
    r"\bwill\s+you\b",
    r"\bi\s+need\b",
    r"\bdo\s+you\s+mind\b",
    r"\bif\s+you\s+could\b",
    r"\bkindly\b",
    r"\bcan\s+we\b",
)


def _find_pattern_matches(patterns: tuple, text: str) -> list[str]:
    """Return unique matched phrases (lowercase, stable order)."""
    if not isinstance(text, str) or not text.strip():
        return []
    found: list[str] = []
    seen: set = set()
    low = text.lower()
    for p in patterns:
        rx = re.compile(p, re.IGNORECASE)
        for m in rx.finditer(low):
            phrase = m.group(0).strip()
            # Collapse internal whitespace runs.
            phrase = re.sub(r"\s+", " ", phrase)
            if phrase and phrase not in seen:
                seen.add(phrase)
                found.append(phrase)
    return found


def _commitment_markers(body: str) -> list[str]:
    return _find_pattern_matches(_COMMITMENT_PATTERNS, body)


def _request_markers(body: str) -> list[str]:
    return _find_pattern_matches(_REQUEST_PATTERNS, body)


# Lexical EP markers. The returned list contains the FLAG NAME
# (canonical, fixed set) rather than the matched keyword — easier to
# consume downstream ("if 'pressure' in ep_flags:").
_EP_FLAGS: dict[str, tuple] = {
    "pressure":      ("urgent", "asap", "critical", "emergency",
                      "immediate", "rush", "now"),
    "tension":       ("disagree", "concern", "issue", "problem",
                      "frustrat", "upset", "unhappy", "angry"),
    "drift":         ("change", "shift", "different", "moved on",
                      "no longer", "pivot", "reconsider"),
    "trust":         ("trust", "rely", "confident", "honest",
                      "promise", "guarantee"),
    "alignment":     ("agree", "aligned", "on the same page",
                      "consensus", "together", "in sync"),
    "contradiction": (" but ", "however", "actually", "contrary",
                      "instead", "on the other hand"),
}


def _ep_flags(subject: str, body: str) -> list[str]:
    """Lexical EP flag set. Returns the canonical flag NAMES present."""
    text = f" {subject} \n {body} ".lower()
    flags: list[str] = []
    for flag, keywords in _EP_FLAGS.items():
        if any(kw in text for kw in keywords):
            flags.append(flag)
    return flags


# Thread key: stable id derived from the normalised subject. Used by
# downstream consumers to group reply chains. Strips up to 3 layers
# of "Re:"/"Fwd:"/"Fw:" prefixes before hashing.
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(?:re|fwd?|fw)\s*:\s*", re.IGNORECASE)


def _thread_key(subject: str) -> str:
    """Normalise subject (strip Re:/Fwd: prefixes) and hash to 16 chars."""
    s = subject if isinstance(subject, str) else ""
    s = s.strip()
    for _ in range(3):
        m = _SUBJECT_PREFIX_RE.match(s)
        if not m:
            break
        s = s[m.end():].strip()
    normalized = " ".join(s.lower().split())
    if not normalized:
        normalized = "<empty-subject>"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def normalize_email(email: dict, user_id: str = "system") -> dict:
    """Convert a parsed email dict into the canonical packet schema.

    Deterministic: identical input produces identical output (no LLM,
    no time-dependent fields inside the packet). Missing fields get
    sensible defaults.

    Returns a dict with exactly the ``PACKET_KEYS`` keys.

    Note: ``user_id`` is accepted for symmetry with
    ``personal_news_basin.normalize_headline`` and to permit per-user
    customisation later (e.g., personal marker dictionaries). Phase 2
    does not use it.
    """
    _ = user_id  # reserved for Phase-2.x personalisation
    if not isinstance(email, dict):
        email = {}

    from_ = str(email.get("from") or "").strip()

    to_raw = email.get("to")
    if isinstance(to_raw, str):
        to_ = _split_addresses(to_raw)
    elif isinstance(to_raw, list):
        to_ = [str(x).strip() for x in to_raw if str(x).strip()]
    else:
        to_ = []

    cc_raw = email.get("cc")
    if isinstance(cc_raw, str):
        cc_ = _split_addresses(cc_raw)
    elif isinstance(cc_raw, list):
        cc_ = [str(x).strip() for x in cc_raw if str(x).strip()]
    else:
        cc_ = []

    subject = str(email.get("subject") or "").strip()
    body    = str(email.get("body") or "").strip()

    date_raw = email.get("date")
    if isinstance(date_raw, str):
        date_val: Optional[str] = date_raw.strip() or None
    else:
        date_val = None

    return {
        "from":               from_,
        "to":                 to_,
        "cc":                 cc_,
        "subject":            subject,
        "date":               date_val,
        "body":               body,
        "thread_key":         _thread_key(subject),
        "importance":         _classify_importance(subject, body),
        "has_deadline":       _has_deadline(subject, body),
        "commitment_markers": _commitment_markers(body),
        "request_markers":    _request_markers(body),
        "ep_flags":           _ep_flags(subject, body),
    }


# ---------------------------------------------------------------------------
# 3. build_email_dash_envelope
# ---------------------------------------------------------------------------
def build_email_dash_envelope(items: list, user_id: str = "system") -> dict:
    """Wrap normalised email packets in the email_ep_dash envelope.

    Envelope shape:
        {
            "type":         "email_ep_dash",
            "user":         <str>,
            "generated_at": <ISO 8601 string>,
            "items":        [<packet>, ...],
        }
    """
    return {
        "type":         ENVELOPE_TYPE,
        "user":         str(user_id) if user_id is not None else "system",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items":        list(items) if isinstance(items, list) else [],
    }


# ---------------------------------------------------------------------------
# 4. write_to_ingestion_bus
# ---------------------------------------------------------------------------
def write_to_ingestion_bus(envelope: dict) -> str:
    """Submit the envelope as a packet on the ingestion bus.

    Returns the packet_id. Propagates ValueError from the bus when the
    envelope is shape-invalid (caller in run_email_ep_dash catches).
    """
    from ELINS import ingestion_bus
    return ingestion_bus.write_packet(envelope)


# ---------------------------------------------------------------------------
# 5. write_to_library
# ---------------------------------------------------------------------------
def _safe_iso_to_dt(s: Any) -> Optional[datetime]:
    """Best-effort ISO 8601 → datetime. Returns None on failure."""
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def write_to_library(envelope: dict) -> str:
    """Persist a JSON copy of the envelope at
    ``<library_dir>/<YYYY-MM-DD_HHMM>.json``.

    Filename derived from ``envelope.generated_at`` (falls back to now
    on missing/invalid). Creates parent dirs as needed. Returns the
    absolute file path as a string.
    """
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be a dict")

    dir_path = _resolve_library_dir()
    dir_path.mkdir(parents=True, exist_ok=True)

    dt = _safe_iso_to_dt(envelope.get("generated_at"))
    if dt is None:
        dt = datetime.now(timezone.utc)
    fname = dt.strftime("%Y-%m-%d_%H%M") + ".json"
    file_path = dir_path / fname

    file_path.write_text(
        json.dumps(envelope, indent=2, default=str),
        encoding="utf-8",
    )
    return str(file_path)


# ---------------------------------------------------------------------------
# 6. run_email_ep_dash — entrypoint
# ---------------------------------------------------------------------------
def _has_meaningful_content(parsed: dict) -> bool:
    """True iff at least one of from/subject/body is non-empty.

    Used by the entrypoint to decide whether to short-circuit on
    completely empty input (mirrors personal_news_basin's empty-sources
    discipline — don't pollute the archive with vacuous runs).
    """
    if not isinstance(parsed, dict):
        return False
    return bool(
        (parsed.get("from") or "").strip()
        or (parsed.get("subject") or "").strip()
        or (parsed.get("body") or "").strip()
    )


def run_email_ep_dash(raw: str, user_id: str = "system") -> dict:
    """Main entrypoint. Parse one email blob → write.

    Workflow:
        1. Parse the raw blob (always succeeds — returns empty fields
           on garbage).
        2. If nothing meaningful was parsed (from/subject/body all
           empty) → short-circuit to empty envelope with NO writes.
        3. Otherwise normalise to a canonical packet and build the
           envelope.
        4. Write to ingestion bus AND library (each best-effort;
           failures recorded as None on the returned envelope).

    Returns the envelope (with ``_bus_packet_id`` and ``_library_path``
    appended on non-empty runs).
    """
    parsed = parse_email_blob(raw)

    if not _has_meaningful_content(parsed):
        logger.info("email_ep_dash: empty/garbage blob — short-circuiting")
        return build_email_dash_envelope([], user_id)

    packet = normalize_email(parsed, user_id)
    envelope = build_email_dash_envelope([packet], user_id)

    try:
        envelope["_bus_packet_id"] = write_to_ingestion_bus(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("email_ep_dash: bus write failed: %s", e)
        envelope["_bus_packet_id"] = None

    try:
        envelope["_library_path"] = write_to_library(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("email_ep_dash: library write failed: %s", e)
        envelope["_library_path"] = None

    return envelope
