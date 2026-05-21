"""
v36 — Macro-ELINS scheduler + run log.

Runs the macro-ELINS pass periodically: a single global ELINS plus all
six regional ELINS in one tick. Persists the run via
``elins_project.save_daily_run`` (global) + ``save_regional_run``
(regional) and records a macro-run summary via
``elins_project.record_macro_run``.

Cadence is governed by ``elins_scheduler_config``:

    enabled                   bool   (default False)
    cadence                   one of "off"|"daily"|"3x_week"|"weekly"
    external_signal_mode      "cloud_only"|"cloud_perplexity"
    system_user               str    (the synthetic actor for scheduler runs)

The scheduler reads the config every tick so toggling at runtime
takes effect on the next tick. ``_run_macro_elins_once`` is a pure
test hook; it bypasses the cadence gate and always runs.

Public API:
    start_elins_scheduler()
    stop_elins_scheduler()
    _run_macro_elins_once(now_ts=None, *, force=True) -> dict
    is_running() -> bool
    SCHEDULER_TICK_SECONDS
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from ELINS import standard_elins, regional_elins, elins_project
import elins_scheduler_config
import elins_entity_graph
import perplexity_oracle

logger = logging.getLogger("clarityos.elins_scheduler")


# Tick cadence — 5 minutes by default, overridable for tests. Each tick
# checks whether the configured cadence + last-run-ts say the macro pass
# is "due"; ticks that aren't due are no-ops.
SCHEDULER_TICK_SECONDS = float(
    os.environ.get("CLARITYOS_MACRO_TICK_SECONDS", str(5 * 60))
)

# Cadence intervals — seconds between macro passes for each cadence
# value. Used by ``_is_due`` to gate ticks.
_CADENCE_INTERVALS: dict[str, Optional[float]] = {
    "off":     None,                # never due
    "daily":   24 * 3600.0,
    "3x_week": (7 / 3.0) * 24 * 3600.0,   # ~56h between runs
    "weekly":  7 * 24 * 3600.0,
}


_scheduler_started: bool = False
_scheduler_lock: Optional[threading.Lock] = None
_stop_event: Optional[threading.Event] = None


def is_running() -> bool:
    return _scheduler_started


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _is_due(cfg: dict, now: float) -> bool:
    """Return True iff the configured cadence says a new macro pass is
    due now."""
    if not cfg.get("enabled"):
        return False
    cadence = cfg.get("cadence") or "off"
    interval = _CADENCE_INTERVALS.get(cadence)
    if interval is None:
        return False
    last_ts = float(cfg.get("last_run_ts") or 0.0)
    if last_ts <= 0.0:
        return True
    return (now - last_ts) >= interval


def _global_scenario_text() -> str:
    """The scaffold sentence the global ELINS run uses. Stable + lexical
    so the canonical pipeline can extract a meaningful set of primitives
    even when the scheduler runs unattended."""
    return (
        "Global system pressure is rising across institutions; trust between "
        "partners is uneven and tension is sustained across major basins. "
        "Drift in posture and contradiction in policy persist."
    )


_run_id_counter: int = 0
_run_id_lock: Optional[threading.Lock] = None


def _make_run_id(now: float) -> str:
    """Generate a stable, strictly-monotonic run id even when two calls
    happen in the same millisecond (Windows time.time() resolution can
    return identical floats for back-to-back calls). Falls back to a
    plain ms id when the counter starts fresh."""
    global _run_id_counter, _run_id_lock
    if _run_id_lock is None:
        _run_id_lock = threading.Lock()
    with _run_id_lock:
        _run_id_counter += 1
        suffix = _run_id_counter
    return f"macro_{int(now * 1000)}_{suffix}"


def _resolve_eso(region_code: str, *, mode: str, system_user: str) -> Optional[dict]:
    """Resolve the ESO for ``region_code`` according to the scheduler
    config's ``external_signal_mode``.

    "cloud_perplexity"  → fetch the deterministic ESO fixture
    "cloud_only"        → no ESO; pure region-tuned ELINS
    """
    if mode == "cloud_perplexity":
        try:
            return perplexity_oracle.fetch_basin_signals(
                region_code, user=system_user,
            )
        except ValueError:
            return None
    return None


def _run_macro_elins_once(now_ts: Optional[float] = None, *, force: bool = True) -> dict:
    """One macro-ELINS pass. v40: delegates to
    ``intelligence_kernel.run_macro_ELINS``; this wrapper only handles
    the cadence gate + persists ``last_run_ts`` for the next tick.

    ``force`` skips the cadence gate. The background loop calls with
    ``force=False``; tests + the /founder/elins/macro/run_now endpoint
    use ``force=True``.
    """
    import intelligence_kernel  # local import — avoids module-load circular

    now = float(now_ts if now_ts is not None else time.time())
    cfg = elins_scheduler_config.get_config()

    if not force and not _is_due(cfg, now):
        return {
            "ran": False, "reason": "not_due",
            "cadence": cfg.get("cadence"),
            "last_run_ts": cfg.get("last_run_ts"),
        }

    system_user = cfg.get("system_user") or "scheduler"
    ext_mode = cfg.get("external_signal_mode") or "cloud_only"

    summary = intelligence_kernel.run_macro_ELINS(
        system_user, now_ts=now, external_signal_mode=ext_mode,
    )

    # Mirror the cadence + last_run_ts back into the scheduler config so
    # subsequent ticks see the new floor.
    elins_scheduler_config.set_config({"last_run_ts": now})

    return {
        **summary,
        "cadence": cfg.get("cadence"),
    }


def _scheduler_loop():  # pragma: no cover — spawned in a daemon thread
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            _run_macro_elins_once(force=False)
        except Exception as e:
            logger.warning("macro scheduler tick failed err=%s", e)
        # ``Event.wait`` returns True on set, lets stop_elins_scheduler
        # interrupt cleanly without a long sleep.
        if _stop_event.wait(SCHEDULER_TICK_SECONDS):
            return


def start_elins_scheduler() -> bool:
    """Lazy boot. Daemon thread; one per process; idempotent. Returns
    True iff a thread was actually started this call."""
    global _scheduler_started, _scheduler_lock, _stop_event
    if _scheduler_started:
        return False
    if _scheduler_lock is None:
        _scheduler_lock = threading.Lock()
    with _scheduler_lock:
        if _scheduler_started:
            return False
        _stop_event = threading.Event()
        t = threading.Thread(
            target=_scheduler_loop,
            name="elins-macro-scheduler",
            daemon=True,
        )
        t.start()
        _scheduler_started = True
        logger.info(
            "macro elins scheduler started (tick=%.0fs)", SCHEDULER_TICK_SECONDS,
        )
        return True


def stop_elins_scheduler() -> bool:
    """Signal the scheduler loop to exit. Idempotent. Returns True iff
    a running scheduler was actually signalled to stop."""
    global _scheduler_started, _stop_event
    if not _scheduler_started:
        return False
    if _stop_event is not None:
        _stop_event.set()
    _scheduler_started = False
    return True


def _reset_for_tests() -> None:
    """Reset module-level state. Tests call this to clear the singleton
    flag between runs without leaking real daemon threads."""
    global _scheduler_started, _scheduler_lock, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    _scheduler_started = False
    _scheduler_lock = None
    _stop_event = None
