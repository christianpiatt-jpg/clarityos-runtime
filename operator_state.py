"""
Operator State — per-user preference, signal-mode, and interaction history.

Persistence is delegated to memory_vault (v46+); the legacy in-memory
fast-path is gone — every read walks the per-user vault. The mock
backend is itself in-memory and the fs/sqlite backends keep per-user
files small, so the cost is bounded. ``migrate_operator_state_to_vault``
provides a one-shot upgrade from a legacy in-memory snapshot.

Public API (constants):
    STATE_VERSION
    HISTORY_MAX
    TOPIC_MAX_LEN
    PREFERRED_DECAY
    PREFERRED_INCREMENT
    VALID_SIGNAL_MODES

Public API (functions):
    get_operator_state(user_id) -> dict
    update_operator_state(user_id, patch) -> dict
    set_external_signal_mode(user_id, mode) -> dict
    set_el_ins_per_turn(user_id, enabled) -> dict            # v69
    get_el_ins_per_turn(user_id) -> bool                     # v69
    set_preferred_model(user_id, model_id) -> dict           # v44
    record_model_used(user_id, model_id) -> dict             # v44
    bump_local_model_usage(user_id, *, by=1) -> dict         # v45
    record_elins_interaction(user_id, elins_id, context) -> dict
    record_g_run(user_id, g_id, context) -> dict
    related_runs(user_id, *, region=None, topic=None, limit=5) -> list[dict]
    continuity_section(user_id, *, last_topics_n=3) -> dict
    continuity_context(user_id) -> dict
    migrate_operator_state_to_vault(user_id, legacy_state) -> dict

State shape (13 fields, dict-insertion order, returned by get_operator_state):
    user_id:                  str
    created_ts:               float
    last_active_ts:           float
    external_signal_mode:     str          # one of VALID_SIGNAL_MODES
    preferred_domains:        dict[str, float]
    preferred_regions:        dict[str, float]
    preferred_model:          Optional[str]
    last_model_used:          Optional[str]
    local_model_usage_count:  int
    el_ins_per_turn:          bool         # v69; default False
    elins_history:            list[dict]   # oldest→newest, capped at HISTORY_MAX
    g_history:                list[dict]   # oldest→newest, capped at HISTORY_MAX
    version:                  str          # always STATE_VERSION
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import memory_vault
import runtime_privacy

logger = logging.getLogger("clarityos.operator_state")

STATE_VERSION: str = "operator_state.v46.1"

HISTORY_MAX: int = 200
TOPIC_MAX_LEN: int = 200
PREFERRED_DECAY: float = 0.9
PREFERRED_INCREMENT: float = 1.0

VALID_SIGNAL_MODES: tuple = ("cloud_only", "cloud_perplexity")

# Vault key prefixes — the canonical way to find operator-state data
# inside the per-user vault.
_OS_PREFIX:    str = "operator_state."
_ELINS_PREFIX: str = "elins."
_GRUNS_PREFIX: str = "g_runs."

# Field names stored under operator_state.* (one vault key each).
_OS_FIELDS_DEFAULTS: dict = {
    "created_ts":            None,    # populated lazily on first read
    "last_active_ts":        None,
    "external_signal_mode":  "cloud_only",
    "preferred_domains":     {},
    "preferred_regions":     {},
    "preferred_model":       None,
    "last_model_used":       None,
    "local_model_usage_count": 0,
    # v69 / Unit 74 — EL/INS per-turn analysis opt-in. Default off so
    # existing operators don't unknowingly pay the analysis cost.
    # Operators set this via set_el_ins_per_turn(); the kernel reads
    # it from intelligence_kernel.run_thread_message to decide whether
    # to run a deterministic EL/INS analysis on the user message and
    # store the result in el_ins_store under source="per_turn".
    "el_ins_per_turn":       False,
}

# Lock for the per-user history sequence counter so concurrent
# record_* calls produce unique vault keys even within the same ms.
_SEQ_LOCK = threading.Lock()
_HISTORY_SEQ: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> float:
    return time.time()


def _trim_topic(topic: Optional[str]) -> str:
    """PASS-4 FIX-P5 — Thin wrapper over ``runtime_privacy.topic_trim``
    so every existing call site keeps working. The centralised helper
    enforces the same strip + ``TOPIC_MAX_LEN`` cap that this function
    used to implement inline."""
    return runtime_privacy.topic_trim(topic)


def _next_seq(prefix: str) -> int:
    """Per-namespace, process-wide monotonic counter so two writes in
    the same ms still produce distinct vault keys."""
    with _SEQ_LOCK:
        n = _HISTORY_SEQ.get(prefix, 0) + 1
        _HISTORY_SEQ[prefix] = n
        return n


def _make_history_key(prefix: str, ts: float) -> str:
    """Build a vault key for an ELINS or #G history entry. Format:
    ``{prefix}{ts_ms}_{seq}`` so the keys sort lexicographically into
    chronological order (within the same prefix)."""
    seq = _next_seq(prefix)
    return f"{prefix}{int(ts * 1000)}_{seq:06d}"


def _strip_forbidden(ctx: dict) -> dict:
    """Remove raw-text fields from a metadata dict before persistence.
    Mirrors the v39 contract — operator_state never carries prompt
    bodies, only metadata. Applied by ``record_elins_interaction``,
    ``record_g_run``, and (as of PASS-4 FIX-P2)
    ``migrate_operator_state_to_vault`` — the migration path must
    enforce the same redaction as live writes so legacy snapshots
    cannot smuggle prompt bodies into the vault."""
    out = dict(ctx or {})
    for forbidden in ("text", "scenario_text", "input_text", "raw_text"):
        out.pop(forbidden, None)
    return out


def _decay_and_bump(weights: dict, key: Optional[str]) -> dict:
    """Apply exponential decay to all entries, then bump ``key``. Pure
    dict→dict transformation. Keys with weight under 0.001 are pruned
    so the dict doesn't accumulate floor noise forever."""
    out: dict = {}
    for k, v in (weights or {}).items():
        try:
            new_v = float(v) * PREFERRED_DECAY
        except (TypeError, ValueError):
            continue
        if new_v >= 0.001:
            out[str(k)] = round(new_v, 4)
    if key:
        out[str(key)] = round(out.get(str(key), 0.0) + PREFERRED_INCREMENT, 4)
    return out


def _list_history(all_entries: dict, prefix: str) -> list[dict]:
    """Return history entries sorted oldest→newest, capped at HISTORY_MAX."""
    out = [v for k, v in all_entries.items()
           if k.startswith(prefix) and isinstance(v, dict)]
    out.sort(key=lambda x: float(x.get("ts") or 0.0))
    return out[-HISTORY_MAX:]


def _prune_history(user_id: str, prefix: str) -> None:
    """Trim oldest entries beyond HISTORY_MAX. Called after record_*
    so the vault doesn't grow unbounded."""
    all_entries = memory_vault.vault_list(user_id)
    keys = [k for k in all_entries if k.startswith(prefix)]
    if len(keys) <= HISTORY_MAX:
        return
    # Sort by ts (oldest first), drop oldest beyond cap.
    sorted_keys = sorted(
        keys,
        key=lambda k: float((all_entries.get(k) or {}).get("ts") or 0.0),
    )
    excess = len(keys) - HISTORY_MAX
    for k in sorted_keys[:excess]:
        memory_vault.vault_delete(user_id, k)


# ---------------------------------------------------------------------------
# Public — get / update
# ---------------------------------------------------------------------------
def get_operator_state(user_id: str) -> dict:
    """Reconstruct the canonical operator-state dict from the vault.
    Initialises ``created_ts`` + ``last_active_ts`` on the first call."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")

    memory_vault.vault_init(user_id)
    all_entries = memory_vault.vault_list(user_id)

    # operator_state.* fields — fall back to defaults when missing.
    created_ts = all_entries.get(_OS_PREFIX + "created_ts")
    if not isinstance(created_ts, (int, float)):
        created_ts = _now()
        memory_vault.vault_put(user_id, _OS_PREFIX + "created_ts", created_ts)

    last_active_ts = all_entries.get(_OS_PREFIX + "last_active_ts")
    if not isinstance(last_active_ts, (int, float)):
        last_active_ts = float(created_ts)

    mode = all_entries.get(_OS_PREFIX + "external_signal_mode")
    if mode not in VALID_SIGNAL_MODES:
        mode = "cloud_only"

    preferred_domains = all_entries.get(_OS_PREFIX + "preferred_domains") or {}
    if not isinstance(preferred_domains, dict):
        preferred_domains = {}
    preferred_domains = {str(k): float(v) for k, v in preferred_domains.items()
                         if isinstance(v, (int, float))}

    preferred_regions = all_entries.get(_OS_PREFIX + "preferred_regions") or {}
    if not isinstance(preferred_regions, dict):
        preferred_regions = {}
    preferred_regions = {str(k): float(v) for k, v in preferred_regions.items()
                         if isinstance(v, (int, float))}

    preferred_model = all_entries.get(_OS_PREFIX + "preferred_model")
    if not isinstance(preferred_model, str) or not preferred_model:
        preferred_model = None

    last_model_used = all_entries.get(_OS_PREFIX + "last_model_used")
    if not isinstance(last_model_used, str) or not last_model_used:
        last_model_used = None

    raw_lm = all_entries.get(_OS_PREFIX + "local_model_usage_count")
    try:
        local_count = max(0, int(raw_lm)) if raw_lm is not None else 0
    except (TypeError, ValueError):
        local_count = 0

    # v69 / Unit 74 — EL/INS per-turn flag.
    el_ins_per_turn = bool(
        all_entries.get(_OS_PREFIX + "el_ins_per_turn") or False,
    )

    return {
        "user_id":               user_id,
        "created_ts":            float(created_ts),
        "last_active_ts":        float(last_active_ts),
        "external_signal_mode":  mode,
        "preferred_domains":     preferred_domains,
        "preferred_regions":     preferred_regions,
        "preferred_model":       preferred_model,
        "last_model_used":       last_model_used,
        "local_model_usage_count": local_count,
        "el_ins_per_turn":       el_ins_per_turn,
        "elins_history":         _list_history(all_entries, _ELINS_PREFIX),
        "g_history":             _list_history(all_entries, _GRUNS_PREFIX),
        "version":               STATE_VERSION,
    }


def _touch_last_active(user_id: str) -> None:
    memory_vault.vault_put(user_id, _OS_PREFIX + "last_active_ts", _now())


def update_operator_state(user_id: str, patch: dict) -> dict:
    """Merge ``patch`` into the user's state. Only known keys are applied.
    Unknown keys are silently dropped. Returns the new state."""
    if not isinstance(patch, dict):
        raise ValueError("patch must be a dict")
    # Ensure user state exists (this also writes created_ts on first call).
    cur = get_operator_state(user_id)

    if "external_signal_mode" in patch:
        mode = patch["external_signal_mode"]
        if mode in VALID_SIGNAL_MODES:
            memory_vault.vault_put(user_id, _OS_PREFIX + "external_signal_mode", mode)

    if "preferred_model" in patch:
        pm = patch["preferred_model"]
        if pm is None or pm == "":
            memory_vault.vault_delete(user_id, _OS_PREFIX + "preferred_model")
        elif isinstance(pm, str):
            memory_vault.vault_put(user_id, _OS_PREFIX + "preferred_model", pm)

    if "last_model_used" in patch and isinstance(patch.get("last_model_used"), str):
        memory_vault.vault_put(
            user_id, _OS_PREFIX + "last_model_used", patch["last_model_used"],
        )

    for k in ("preferred_domains", "preferred_regions"):
        if k in patch and isinstance(patch[k], dict):
            merged = dict(cur.get(k) or {})
            for kk, vv in patch[k].items():
                try:
                    merged[str(kk)] = float(vv)
                except (TypeError, ValueError):
                    continue
            memory_vault.vault_put(user_id, _OS_PREFIX + k, merged)

    # v69 / Unit 74 — EL/INS per-turn opt-in.
    if "el_ins_per_turn" in patch:
        memory_vault.vault_put(
            user_id, _OS_PREFIX + "el_ins_per_turn",
            bool(patch["el_ins_per_turn"]),
        )

    _touch_last_active(user_id)
    return get_operator_state(user_id)


def set_external_signal_mode(user_id: str, mode: str) -> dict:
    if mode not in VALID_SIGNAL_MODES:
        raise ValueError(f"mode must be one of {VALID_SIGNAL_MODES!r}")
    return update_operator_state(user_id, {"external_signal_mode": mode})


# ---------------------------------------------------------------------------
# v69 / Unit 74 — EL/INS per-turn opt-in
# ---------------------------------------------------------------------------
def set_el_ins_per_turn(user_id: str, enabled: bool) -> dict:
    """Toggle the per-turn EL/INS analysis hook for ``user_id``.

    When enabled, ``intelligence_kernel.run_thread_message`` runs a
    deterministic EL/INS pass on the latest user message after the
    assistant turn is persisted and stores the result in
    ``el_ins_store`` with ``source="per_turn"``.

    Default is False so existing operators don't silently pay the
    analysis cost. The flag is stored under ``operator_state.el_ins_per_turn``.
    """
    return update_operator_state(user_id, {"el_ins_per_turn": bool(enabled)})


def get_el_ins_per_turn(user_id: str) -> bool:
    """Read the EL/INS per-turn flag for ``user_id``. Returns False for
    operators that never set it."""
    state = get_operator_state(user_id)
    return bool(state.get("el_ins_per_turn"))


def set_preferred_model(user_id: str, model_id: Optional[str]) -> dict:
    """Persist the user's preferred model. ``model_id`` is validated
    against ``model_router.SUPPORTED_MODELS``; passing None clears the
    preference (router falls back to task default)."""
    # Touch state so created_ts exists.
    get_operator_state(user_id)
    if model_id is None or (isinstance(model_id, str) and model_id == ""):
        memory_vault.vault_delete(user_id, _OS_PREFIX + "preferred_model")
    else:
        # Lazy import to avoid circular dep at module load.
        import model_router
        if not model_router.is_valid_model(model_id):
            raise ValueError(
                f"unknown model_id {model_id!r}; expected one of "
                f"{list(model_router.SUPPORTED_MODELS)!r}",
            )
        memory_vault.vault_put(user_id, _OS_PREFIX + "preferred_model", model_id)
    _touch_last_active(user_id)
    return get_operator_state(user_id)


def record_model_used(user_id: str, model_id: Optional[str]) -> dict:
    """Append the most-recently-used model_id onto the user's state."""
    if not user_id:
        return {}
    get_operator_state(user_id)
    if isinstance(model_id, str) and model_id:
        memory_vault.vault_put(user_id, _OS_PREFIX + "last_model_used", model_id)
        _touch_last_active(user_id)
    return get_operator_state(user_id)


def bump_local_model_usage(user_id: str, *, by: int = 1) -> dict:
    """Increment per-user ``local_model_usage_count``."""
    if not user_id:
        return {}
    try:
        delta = max(0, int(by))
    except (TypeError, ValueError):
        delta = 0
    state = get_operator_state(user_id)
    cur = int(state.get("local_model_usage_count") or 0)
    memory_vault.vault_put(
        user_id, _OS_PREFIX + "local_model_usage_count", cur + delta,
    )
    _touch_last_active(user_id)
    return get_operator_state(user_id)


# ---------------------------------------------------------------------------
# Public — record_elins_interaction / record_g_run
# ---------------------------------------------------------------------------
def record_elins_interaction(
    user_id: str, elins_id: Optional[str], context: Optional[dict] = None,
) -> dict:
    """Append an ELINS interaction as an individual vault entry under
    ``elins.{ts_ms}_{seq}``. ``context`` is metadata-only:
        ``{"topic": str?, "region": str?, "domain": str?, "kind": str?}``.
    Raw prompt text MUST NOT be passed in; the field is rejected."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    ctx = _strip_forbidden(context or {})
    state = get_operator_state(user_id)   # ensures init
    ts = _now()
    entry = {
        "ts":       ts,
        "elins_id": str(elins_id or ""),
        "topic":    _trim_topic(ctx.get("topic")),
        "region":   ctx.get("region"),
        "kind":     ctx.get("kind") or ("regional" if ctx.get("region") else "global"),
    }
    memory_vault.vault_put(user_id, _make_history_key(_ELINS_PREFIX, ts), entry)

    # Update preferred regions/domains via decay+bump.
    new_regions = _decay_and_bump(
        state.get("preferred_regions") or {}, ctx.get("region"),
    )
    new_domains = _decay_and_bump(
        state.get("preferred_domains") or {}, ctx.get("domain"),
    )
    memory_vault.vault_put(user_id, _OS_PREFIX + "preferred_regions", new_regions)
    memory_vault.vault_put(user_id, _OS_PREFIX + "preferred_domains", new_domains)

    _touch_last_active(user_id)
    _prune_history(user_id, _ELINS_PREFIX)
    return get_operator_state(user_id)


def record_g_run(
    user_id: str, g_id: Optional[str], context: Optional[dict] = None,
) -> dict:
    """Append a #G run as a vault entry under ``g_runs.{ts_ms}_{seq}``."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    ctx = _strip_forbidden(context or {})
    state = get_operator_state(user_id)   # ensures init
    ts = _now()
    entry = {
        "ts":    ts,
        "g_id":  str(g_id or ""),
        "mode":  str(ctx.get("mode") or "G"),
        "topic": _trim_topic(ctx.get("topic")),
    }
    memory_vault.vault_put(user_id, _make_history_key(_GRUNS_PREFIX, ts), entry)
    if ctx.get("domain"):
        new_domains = _decay_and_bump(
            state.get("preferred_domains") or {}, ctx["domain"],
        )
        memory_vault.vault_put(user_id, _OS_PREFIX + "preferred_domains", new_domains)
    _touch_last_active(user_id)
    _prune_history(user_id, _GRUNS_PREFIX)
    return get_operator_state(user_id)


# ---------------------------------------------------------------------------
# Read-side helpers (used by the dashboard + ELINSInspector)
# ---------------------------------------------------------------------------
def related_runs(
    user_id: str,
    *,
    region: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    state = get_operator_state(user_id)
    out: list[dict] = []
    topic_lower = (topic or "").strip().lower()
    for entry in reversed(state.get("elins_history") or []):
        match = False
        if region and entry.get("region") == region:
            match = True
        if topic_lower:
            t = (entry.get("topic") or "").lower()
            if t and topic_lower in t:
                match = True
        if not region and not topic:
            match = True
        if match:
            out.append(dict(entry))
            if len(out) >= max(1, int(limit)):
                break
    return out


def continuity_section(user_id: str, *, last_topics_n: int = 3) -> dict:
    state = get_operator_state(user_id)
    last_topics: list[str] = []
    for entry in reversed(state.get("elins_history") or []):
        t = entry.get("topic")
        if t and t not in last_topics:
            last_topics.append(t)
        if len(last_topics) >= last_topics_n:
            break
    pd = state.get("preferred_domains") or {}
    pr = state.get("preferred_regions") or {}
    pd_sorted = sorted(pd.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    pr_sorted = sorted(pr.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {
        "last_topics": last_topics,
        "preferred_domains": [{"name": k, "weight": v} for k, v in pd_sorted],
        "preferred_regions": [{"name": k, "weight": v} for k, v in pr_sorted],
        "external_signal_mode": state.get("external_signal_mode"),
        "history_count": len(state.get("elins_history") or []),
        "g_count": len(state.get("g_history") or []),
    }


def continuity_context(user_id: str) -> dict:
    sec = continuity_section(user_id)
    state = get_operator_state(user_id)
    last_region = None
    for entry in reversed(state.get("elins_history") or []):
        if entry.get("region"):
            last_region = entry["region"]
            break
    return {
        **sec,
        "last_region": last_region,
        "user_id": user_id,
    }


# ---------------------------------------------------------------------------
# Migration helper — for one-shot upgrades from legacy in-memory state
# ---------------------------------------------------------------------------
def migrate_operator_state_to_vault(user_id: str, legacy_state: dict) -> dict:
    """Take a legacy v45-style operator state dict and write each field
    into the vault under the v46 schema. Idempotent: re-running with
    the same input is safe; existing vault entries are overwritten,
    and ELINS / #G history entries are recreated.

    PASS-4 FIX-P2 — Each legacy history entry is now passed through
    ``_strip_forbidden`` before being persisted (closing the gap where
    raw text-bearing fields like ``text`` / ``scenario_text`` /
    ``input_text`` / ``raw_text`` would survive migration even though
    live writes via ``record_elins_interaction`` / ``record_g_run``
    would strip them). Each history list is also pre-capped at
    ``HISTORY_MAX`` (oldest entries dropped, newest preserved) so the
    migration cannot persist more rows than the runtime read path
    would ever surface — matching the live pruning behaviour of
    ``_prune_history``.

    Returns the resulting v46 state via ``get_operator_state``.
    """
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(legacy_state, dict):
        raise ValueError("legacy_state must be a dict")

    memory_vault.vault_init(user_id)

    # Scalar / dict fields.
    for fld in (
        "external_signal_mode", "preferred_domains", "preferred_regions",
        "preferred_model", "last_model_used",
    ):
        if fld in legacy_state and legacy_state[fld] not in (None, ""):
            memory_vault.vault_put(user_id, _OS_PREFIX + fld, legacy_state[fld])

    if "local_model_usage_count" in legacy_state:
        try:
            memory_vault.vault_put(
                user_id, _OS_PREFIX + "local_model_usage_count",
                max(0, int(legacy_state["local_model_usage_count"] or 0)),
            )
        except (TypeError, ValueError):
            pass

    if "created_ts" in legacy_state and isinstance(legacy_state["created_ts"], (int, float)):
        memory_vault.vault_put(user_id, _OS_PREFIX + "created_ts", float(legacy_state["created_ts"]))

    if "last_active_ts" in legacy_state and isinstance(legacy_state["last_active_ts"], (int, float)):
        memory_vault.vault_put(user_id, _OS_PREFIX + "last_active_ts", float(legacy_state["last_active_ts"]))

    # History entries.
    #
    # PASS-4 FIX-P2 — Three steps per history bucket, applied in this
    # exact order so the result is identical to what a sequence of
    # live record_* calls would have produced:
    #   1. Drop non-dict entries (defensive — same as the prior code).
    #   2. Run each entry through ``_strip_forbidden`` so prompt bodies
    #      and other text-bearing fields are dropped before they ever
    #      reach the vault.
    #   3. Sort oldest→newest by ``ts`` and keep only the most-recent
    #      ``HISTORY_MAX`` entries (mirrors ``_list_history`` /
    #      ``_prune_history`` semantics).
    def _prepare_history(entries):
        scrubbed = [
            _strip_forbidden(e) for e in (entries or [])
            if isinstance(e, dict)
        ]
        scrubbed.sort(key=lambda x: float(x.get("ts") or 0.0))
        return scrubbed[-HISTORY_MAX:]

    for entry in _prepare_history(legacy_state.get("elins_history")):
        ts = float(entry.get("ts") or _now())
        memory_vault.vault_put(
            user_id, _make_history_key(_ELINS_PREFIX, ts), entry,
        )
    for entry in _prepare_history(legacy_state.get("g_history")):
        ts = float(entry.get("ts") or _now())
        memory_vault.vault_put(
            user_id, _make_history_key(_GRUNS_PREFIX, ts), entry,
        )

    return get_operator_state(user_id)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    """Wipe the per-user history sequence counter. The vault itself is
    reset by ``memory_vault._reset_for_tests`` (the conftest hook
    invokes both)."""
    global _HISTORY_SEQ
    with _SEQ_LOCK:
        _HISTORY_SEQ = {}
