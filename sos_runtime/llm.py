"""
LLM dispatch for SOS Runtime.

Single entry point: ``call_claude(message, context)`` → ``{reply, raw}``.

Two modes:
    real — Anthropic SDK with ``SOS_ANTHROPIC_API_KEY`` env var.
    fake — deterministic echo (no network, no key needed). Used in
           tests + dev paths.

Mode selection:
    1. ``SOS_LLM_MODE`` env var (``real`` | ``fake``) if set.
    2. ``fake`` when ``SOS_BACKEND=memory`` (test convention).
    3. ``real`` when ``SOS_ANTHROPIC_API_KEY`` is set.
    4. ``fake`` otherwise — never raises on missing key, just degrades
       to deterministic so the WordPress connector keeps working in a
       dev environment with no Anthropic access.

Per the SOS design call, this is intentionally NOT routed through
ClarityOS ``model_router``. SOS Runtime stays self-contained.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("sos_runtime.llm")

DEFAULT_MODEL = "claude-3-7-sonnet-latest"
DEFAULT_MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def _mode_name() -> str:
    explicit = (os.environ.get("SOS_LLM_MODE") or "").strip().lower()
    if explicit in ("real", "fake"):
        return explicit
    if (os.environ.get("SOS_BACKEND") or "").lower() == "memory":
        return "fake"
    if (os.environ.get("SOS_ANTHROPIC_API_KEY") or "").strip():
        return "real"
    return "fake"


def _model_id() -> str:
    return (
        os.environ.get("SOS_ANTHROPIC_MODEL") or DEFAULT_MODEL
    ).strip()


# ---------------------------------------------------------------------------
# Fake dispatcher
# ---------------------------------------------------------------------------
def _fake_call(message: str, context: dict) -> dict:
    """Deterministic echo. Never raises. Used in tests + dev paths
    + as the production fallback when no key is set."""
    preview = message.strip()
    if len(preview) > 400:
        preview = preview[:400] + "…"
    keys = sorted((context or {}).keys())
    reply = (
        f"[sos-runtime fake mode] received {len(preview)} chars; "
        f"context keys: {keys or '(none)'}; "
        f"echo: {preview}"
    )
    return {
        "reply":      reply,
        "model_id":   "fake:deterministic",
        "mock":       True,
        "ts":         time.time(),
        "raw":        {"echo": preview, "context_keys": keys},
    }


# ---------------------------------------------------------------------------
# Real dispatcher (Anthropic SDK)
# ---------------------------------------------------------------------------
def _real_call(message: str, context: dict) -> dict:   # pragma: no cover (live)
    """Anthropic SDK call. Wrapped in a try/except — any provider
    failure falls back to the fake dispatcher so the request path
    never bubbles a 5xx for an upstream model hiccup."""
    try:
        import anthropic   # type: ignore
    except ImportError:
        logger.warning(
            "anthropic SDK not installed; falling back to fake mode."
        )
        return _fake_call(message, context)

    api_key = os.environ.get("SOS_ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning(
            "SOS_ANTHROPIC_API_KEY unset; falling back to fake mode."
        )
        return _fake_call(message, context)

    model = _model_id()
    max_tokens = DEFAULT_MAX_TOKENS

    # Compose a single user-role message. Context is serialised into
    # the prompt prologue so the model sees structured framing.
    if context:
        context_block = "\n".join(
            f"- {k}: {v!r}" for k, v in sorted(context.items())
        )
        prompt_text = (
            "Context provided by the operator's WordPress shell:\n"
            f"{context_block}\n\n"
            f"Operator message:\n{message}"
        )
    else:
        prompt_text = message

    started = time.time()
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt_text}],
        )
        # Anthropic returns a list of content blocks; concatenate
        # text blocks (the typical shape for short replies).
        parts: list[str] = []
        for block in (msg.content or []):
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
        reply = "".join(parts).strip()
        return {
            "reply":    reply or "(empty model response)",
            "model_id": model,
            "mock":     False,
            "ts":       started,
            "raw": {
                "id":            getattr(msg, "id", None),
                "stop_reason":   getattr(msg, "stop_reason", None),
                "usage":         getattr(msg, "usage", None).__dict__
                                  if getattr(msg, "usage", None) else None,
            },
        }
    except Exception as e:   # pragma: no cover (network path)
        logger.warning(
            "anthropic call failed model=%s err=%s — falling back to fake.",
            model, e,
        )
        return _fake_call(message, context)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def call_claude(message: str, context: Optional[dict] = None) -> dict:
    """Single LLM entry point. Never raises.

    Returns::

        {
          "reply":    str,
          "model_id": str,
          "mock":     bool,
          "ts":       float,
          "raw":      dict,
        }
    """
    if not isinstance(message, str) or not message.strip():
        # Mirror the contract: empty input → empty echo, not an exception.
        return _fake_call("", context or {})
    ctx = dict(context or {})
    if _mode_name() == "real":
        return _real_call(message, ctx)
    return _fake_call(message, ctx)


def llm_status() -> dict:
    """Introspection helper for the /health surface — confirms which
    mode is active without leaking the API key."""
    mode = _mode_name()
    return {
        "mode":     mode,
        "model_id": _model_id() if mode == "real" else "fake:deterministic",
        "configured": bool(
            (os.environ.get("SOS_ANTHROPIC_API_KEY") or "").strip()
        ),
    }
