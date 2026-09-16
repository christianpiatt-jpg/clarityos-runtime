"""
PASS-4 FIX-P5 — Centralised logging-redaction helpers.

A small set of pure string utilities for redacting potentially-sensitive
identifiers and content before they reach log streams. Used by the
runtime modules (``app``, ``intelligence_kernel``, ``model_router``,
``operator_state``, ``memory_vault``) wherever a user_id, session_id,
prompt body, topic string, or event id might otherwise land in a log
line in full.

Design notes
------------
* No logging happens inside this module — every helper is a pure
  string function so unit tests can run them in isolation and callers
  stay in control of when (and at what level) to log.
* The trailing ``"..."`` ellipsis on truncated refs is intentional —
  it makes redaction visible to a log reader rather than silently
  shortening a token that might still look like a valid id.
* The lengths are tuned to be useful for correlation (matching log
  lines across modules during incident response) without restoring
  the unredacted identifier.

Public constants
----------------
    SESSION_REF_LEN         — first-N chars of a session_id kept in logs
    USER_REF_LEN            — first-N chars of a user_id kept in logs
    MOCK_PROMPT_PREVIEW_LEN — first-N chars of a prompt body kept in
                              mock-result payloads (matches the
                              v44 model_router mock contract)
    TOPIC_MAX_LEN           — operator_state topic cap (matches the
                              v39 contract; mirrored here so a future
                              refactor can move the constant cleanly)
    EVENT_ID_SHORT_LEN      — first-N chars of an event id (Stripe
                              ``evt_*``, checkout session ``cs_*``)
                              kept in audit metadata

Public helpers
--------------
    session_ref(session_id)
    user_ref(user_id)
    prompt_preview(text)
    topic_trim(topic)
    event_ref(event_id)
    scrub_credentials(text)   -- #284
"""
from __future__ import annotations

import re
from typing import Any, Optional

SESSION_REF_LEN:         int = 8
USER_REF_LEN:            int = 8
MOCK_PROMPT_PREVIEW_LEN: int = 60
TOPIC_MAX_LEN:           int = 200
EVENT_ID_SHORT_LEN:      int = 24

_NONE_MARKER: str = "<none>"


def session_ref(session_id: Optional[str]) -> str:
    """Return a redacted reference to a session_id for logging.

    ``None`` / empty / non-string inputs return ``"<none>"`` so log
    lines stay parseable. Otherwise returns the first
    ``SESSION_REF_LEN`` characters followed by ``"..."`` (the
    ellipsis is always appended — even for very short inputs — so a
    log reader can always tell the value is redacted).
    """
    if not session_id or not isinstance(session_id, str):
        return _NONE_MARKER
    return session_id[:SESSION_REF_LEN] + "..."


def user_ref(user_id: Optional[str]) -> str:
    """Return a redacted reference to a user_id for logging.

    Same shape as ``session_ref``: ``"<none>"`` for empty input,
    first ``USER_REF_LEN`` characters + ``"..."`` otherwise.

    #154 -- NO log line in the tree uses this prefix any more: a username
    is an e-mail address, and eight characters of it is most of the local
    part. ``user_hash`` is the log reference; this stays for its pinned
    shape and for callers that are not log lines.
    """
    if not user_id or not isinstance(user_id, str):
        return _NONE_MARKER
    return user_id[:USER_REF_LEN] + "..."


def user_hash(user_id: Optional[str]) -> str:
    """#154 -- the ONE log reference for a user: 16 hex of sha256, the shape
    ``users_store._uref`` and ``auth_magiclink._email_hash`` log (pinned
    equal in tests/test_housekeeping_2026_09_16.py). Every module that logs
    a user goes through this name -- app.py's ``_user_ref`` is this, and the
    kernel, the vault and the router call it directly. ``"<none>"`` for an
    absent or non-string id, the marker ``session_ref`` uses.
    """
    if not user_id or not isinstance(user_id, str):
        return _NONE_MARKER
    import hashlib
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def prompt_preview(text: Optional[str]) -> str:
    """Return a short preview of a prompt body for mock results or
    logs.

    Caps at ``MOCK_PROMPT_PREVIEW_LEN`` characters. ``None`` /
    empty / non-string inputs return an empty string. No truncation
    marker is appended — the v44 model_router mock contract treats
    the preview as opaque, so preserving exact length boundaries
    matches the pre-FIX-P5 mock output byte-for-byte.
    """
    if not text:
        return ""
    return str(text)[:MOCK_PROMPT_PREVIEW_LEN]


def topic_trim(topic: Optional[str]) -> str:
    """Strip whitespace and cap a topic string at ``TOPIC_MAX_LEN``.

    Mirrors the v39 ``operator_state._trim_topic`` contract — topics
    are short, surface-stripped, and never carry prompt bodies.
    Returns ``""`` for ``None`` / empty / non-string input.
    """
    if not topic:
        return ""
    s = str(topic).strip()
    if len(s) > TOPIC_MAX_LEN:
        s = s[:TOPIC_MAX_LEN].rstrip()
    return s


def event_ref(event_id: Optional[Any]) -> str:
    """Return a redacted reference to an event id for logs / metadata.

    Stripe ``evt_*`` / checkout ``cs_*`` / billing webhook ids are
    bounded but still carry internal context, so we keep the leading
    ``EVENT_ID_SHORT_LEN`` characters and append ``"..."`` for any id
    that exceeds the cap. Shorter ids pass through unchanged (no
    ellipsis) so log readers can tell at-a-glance whether the value
    was actually truncated. ``None`` / empty inputs return
    ``"<none>"``.
    """
    if event_id is None:
        return _NONE_MARKER
    s = str(event_id)
    if not s:
        return _NONE_MARKER
    if len(s) <= EVENT_ID_SHORT_LEN:
        return s
    return s[:EVENT_ID_SHORT_LEN] + "..."


# ---------------------------------------------------------------------------
# #284 -- a provider error string on a member wire
# ---------------------------------------------------------------------------
# model_router downgrades a failed real call to a mock and stamps the
# provider's ``str(exc)`` (capped at 200) as ``fallback_error``. Most are
# "HTTP Error 401: Unauthorized" shapes, but the Gemini request URL
# carries ``?key=`` and a urllib ValueError echoes the URL it refused, so
# the string CAN hold a credential. /session showed it to operators
# (#147); the member message route now declares it too, so it is scrubbed
# here first: any URL becomes "[url]" (the Gemini one carries the key in
# its query; the local / ollama ones carry an internal host), then query
# credentials, bearer tokens of any length and the vendor key prefixes
# become "[redacted]". Nothing else about the string changes.
_URL_RE = re.compile(r"(?i)\bhttps?://\S+")
_CRED_QUERY_RE = re.compile(
    r"(?i)\b(key|api[_-]?key|token|secret|authorization|x-api-key)=([^&\s\"'>]+)"
)
_CRED_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_CRED_PREFIX_RE = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}"
    r"|xai-[A-Za-z0-9]{8,}|gsk_[A-Za-z0-9]{8,})"
)


# #303 A5 -- model PROSE on a member wire. The physics body is a model's
# free text about the member's situation; before it reaches glass an
# address, a phone number or a name the member is known by becomes a
# class token. A phone needs separators, a "+" or parentheses so a bare
# integer (a timestamp, a count, a date such as 2026-09-16) is never eaten.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<![\w.-])(?:"
    # the (ddd) ddd-dddd / ddd-ddd-dddd shapes, with an optional country prefix
    r"(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}"
    # an international number behind a "+", never a "+N <date>"
    r"|\+\d{1,3}(?![ .-]?(?:19|20)\d{2}-\d{2}-\d{2})(?:[ .-]?\d{2,4}){2,4}"
    r")(?![\w-])"
)
_NAME_MIN_CHARS = 3


def _name_patterns(names) -> list:
    out: list = []
    for n in names or ():
        if not isinstance(n, str):
            continue
        n = n.strip()
        if len(n) < _NAME_MIN_CHARS:
            continue
        out.append(re.compile(r"(?<!\w)" + re.escape(n) + r"(?!\w)", re.IGNORECASE))
    return out


def scrub_credentials(text: Optional[str], names=None) -> Optional[str]:
    """Return ``text`` with anything credential-shaped replaced by
    ``[redacted]``. ``None`` / empty / non-string returns ``None`` -- an
    absent error stays absent (D5), it never becomes "".

    #303 A5 -- extended: an e-mail address becomes "[email]", a phone
    number "[phone]", and every entry of ``names`` (the member name list
    the caller assembles; whole words, case-insensitive) "[name]"."""
    if not isinstance(text, str) or not text:
        return None
    out = _URL_RE.sub("[url]", text)
    out = _CRED_QUERY_RE.sub(lambda m: f"{m.group(1)}=[redacted]", out)
    out = _CRED_BEARER_RE.sub("bearer [redacted]", out)
    out = _CRED_PREFIX_RE.sub("[redacted]", out)
    out = _EMAIL_RE.sub("[email]", out)
    out = _PHONE_RE.sub("[phone]", out)
    for pat in _name_patterns(names):
        out = pat.sub("[name]", out)
    return out


def scrub_prose(value, names=None, prose_keys=None, _prose=None):
    """#303 A5 -- ``scrub_credentials`` over every string leaf of a nested
    dict / list. A new structure is returned; keys untouched, non-strings
    untouched, an empty string kept empty.

    ``prose_keys``: when given, the NAME pass runs only on string leaves
    under one of these keys (everything beneath a prose key is prose too);
    e-mails and phones are scrubbed everywhere. An enum value is never a
    name, and a name that happens to spell an enum member ("low", "stable")
    must not turn a bearing into "[name]" -- the seal reads the enums after
    this pass. When ``prose_keys`` is None the names run everywhere."""
    in_prose = True if prose_keys is None else bool(_prose)
    if isinstance(value, str):
        return scrub_credentials(value, names if in_prose else None) if value else value
    if isinstance(value, list):
        return [scrub_prose(v, names, prose_keys, in_prose) for v in value]
    if isinstance(value, dict):
        return {
            k: scrub_prose(v, names, prose_keys, in_prose or (prose_keys is not None and k in prose_keys))
            for k, v in value.items()
        }
    return value
