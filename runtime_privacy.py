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
"""
from __future__ import annotations

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
    """
    if not user_id or not isinstance(user_id, str):
        return _NONE_MARKER
    return user_id[:USER_REF_LEN] + "..."


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
