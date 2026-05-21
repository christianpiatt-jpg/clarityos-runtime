"""
v41 — Structured logging for Intelligence Kernel runs.

Single entry point ``log_kernel_run`` that the kernel calls at the end
of every ``run_*``. Output is a JSON-serialisable line on the
``clarityos.kernel.runs`` logger. The helper actively strips fields
that could leak prompt content (``text``, ``scenario_text``,
``input_text``, ``raw_text``, ``prompt``) before serialising.

Public API:
    log_kernel_run(*, kind, user_id, external_signal_mode, eso_source,
                   duration_ms, ok, meta=None, error=None) -> dict
    safe_meta(meta) -> dict          # exposed for tests
    LOG_VERSION
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger("clarityos.kernel.runs")

LOG_VERSION: str = "kernel_logging.v41.1"

# Field names we strip from any meta dict before the log line is
# emitted. The kernel passes only metadata-derived labels in practice,
# but we double-up here so a future caller can't accidentally smuggle a
# raw scenario through.
_FORBIDDEN_META_KEYS: frozenset = frozenset({
    "text", "scenario_text", "input_text", "raw_text", "prompt",
    "html", "body", "raw_body",
})

# Long strings get truncated. Keys allowed to carry short URLs / ids
# stay intact below this cap.
_MAX_META_STR_LEN: int = 200


def safe_meta(meta: Optional[dict]) -> dict:
    """Coerce arbitrary meta into a JSON-clean, prompt-free dict."""
    if not isinstance(meta, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            continue
        if k in _FORBIDDEN_META_KEYS:
            continue
        out[k] = _coerce(v)
    return out


def _coerce(v: Any) -> Any:
    if isinstance(v, str):
        if len(v) > _MAX_META_STR_LEN:
            return v[:_MAX_META_STR_LEN]
        return v
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_coerce(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _coerce(vv) for k, vv in v.items()
                if isinstance(k, str) and k not in _FORBIDDEN_META_KEYS}
    # Fallback: stringify + truncate.
    s = str(v)
    return s if len(s) <= _MAX_META_STR_LEN else s[:_MAX_META_STR_LEN]


def log_kernel_run(
    *,
    kind: str,
    user_id: Optional[str],
    external_signal_mode: Optional[str],
    eso_source: Optional[str],
    duration_ms: Optional[float],
    ok: bool,
    meta: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    """Emit one structured kernel-run line. Returns the record dict so
    callers/tests can assert on it."""
    record: dict[str, Any] = {
        "kind": str(kind or "unknown"),
        "user_id": str(user_id) if user_id is not None else None,
        "external_signal_mode": external_signal_mode,
        "eso_source": eso_source,
        "duration_ms": round(float(duration_ms or 0.0), 2),
        "ok": bool(ok),
        "ts": round(time.time(), 3),
        "version": LOG_VERSION,
    }
    if error is not None:
        record["error"] = str(error)[:_MAX_META_STR_LEN]
    if meta:
        record["meta"] = safe_meta(meta)
    try:
        logger.info("kernel_run %s", json.dumps(record, default=str))
    except Exception:  # pragma: no cover (defensive)
        logger.info(
            "kernel_run kind=%s ok=%s eso_source=%s",
            record["kind"], record["ok"], record["eso_source"],
        )
    return record
