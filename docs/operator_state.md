# Operator State (`operator_state.py`)

## 1. Purpose and role

`operator_state.py` (v39 introduced; v46.1 rewrite — `STATE_VERSION =
"operator_state.v46.1"`) is the **per-user preference, signal-mode,
and interaction-history layer**. It owns every per-user scalar /
dict / history entry that the kernel persists during normal request
processing.

In the runtime call graph it sits **between the kernel and
`memory_vault`**. Persistence is delegated entirely to `memory_vault`
(v46+); the legacy in-memory fast-path is gone. Every read walks the
per-user vault.

Two storage namespaces are owned by this module:

| Namespace prefix | Purpose | Cardinality |
|---|---|---|
| `operator_state.*` | Scalar / dict fields (one vault key per field) | One key per field per user |
| `elins.*` | ELINS interaction history entries | Up to `HISTORY_MAX` per user |
| `g_runs.*` | `#G` run history entries | Up to `HISTORY_MAX` per user |

### Core invariants

1. **`user_id` must be a non-empty string** — `_validate_user` asserts
   at every public-function entry.
2. **ESO mode allow-list** — `VALID_SIGNAL_MODES = ("cloud_only",
   "cloud_perplexity")`; `set_external_signal_mode` raises on invalid
   mode; `get_operator_state` falls back to `"cloud_only"` on invalid
   stored value.
3. **Model id validation via lazy `model_router.is_valid_model`** —
   `set_preferred_model` raises `ValueError` on unknown id.
4. **History cap `HISTORY_MAX = 200` per namespace per user**,
   enforced by `_prune_history` after every `record_*` call.
5. **Forbidden-fields strip** — `_strip_forbidden` removes
   `("text", "scenario_text", "input_text", "raw_text")` from every
   context dict before persistence.
6. **Topic length cap `TOPIC_MAX_LEN = 200` chars** — `_trim_topic`.
7. **Vault key uniqueness within same ms** — `_next_seq(prefix)` is a
   per-namespace process-wide counter under `_SEQ_LOCK`.
8. **Weight decay is monotonic** — every `record_*` call applies
   `PREFERRED_DECAY = 0.9` to all entries, then bumps the named key
   by `PREFERRED_INCREMENT = 1.0`. Floor 0.001.

### Status

| File | Status | Reason |
|---|---|---|
| `operator_state.py` | **CURRENT** | 592 lines · 12 public functions · 22 importers (8 production + 14 tests) |

### Implementation location

- **Source:** `operator_state.py` (592 lines).
- **Imports:** stdlib (`logging`, `threading`, `time`,
  `typing.Optional`) + `memory_vault` (eager — only storage dep) +
  `model_router` (lazy, inside `set_preferred_model` for validation
  only).

---

## 2. Public API surface

12 public functions plus 1 test helper.

| Function | Line | Purpose |
|---|---|---|
| `get_operator_state(user_id)` | 190 | Read full state dict (13 fields) |
| `update_operator_state(user_id, patch)` | 265 | Merge patch (unknown keys silently dropped); returns new state |
| `set_external_signal_mode(user_id, mode)` | 311 | Typed setter; raises `ValueError` on invalid mode |
| `set_el_ins_per_turn(user_id, enabled)` | 320 | v69 per-turn EL/INS analysis opt-in toggle |
| `get_el_ins_per_turn(user_id)` | 334 | bool — defaults to False for operators that never set it |
| `set_preferred_model(user_id, model_id)` | 341 | Validates via lazy `model_router.is_valid_model`; `None`/`""` clears |
| `record_model_used(user_id, model_id)` | 362 | Append `last_model_used`; touches `last_active_ts` |
| `bump_local_model_usage(user_id, *, by=1)` | 373 | Increment `local_model_usage_count` |
| `record_elins_interaction(user_id, elins_id, context=None)` | 393 | Append to `elins.*`; decay/bump `preferred_regions` + `preferred_domains` |
| `record_g_run(user_id, g_id, context=None)` | 429 | Append to `g_runs.*`; decay/bump `preferred_domains` |
| `related_runs(user_id, *, region=None, topic=None, limit=5)` | 458 | Newest-first matching `elins_history` entries |
| `continuity_section(user_id, *, last_topics_n=3)` | 485 | Compact continuity snapshot |
| `continuity_context(user_id)` | 508 | `continuity_section` + `last_region` + `user_id` |
| `migrate_operator_state_to_vault(user_id, legacy_state)` | 526 | One-shot v45 → v46 upgrade (idempotent) |
| `_reset_memory_for_tests()` | 586 | Test-only — wipes `_HISTORY_SEQ` counter (vault reset is separate) |

### Module constants

| Name | Value | Purpose |
|---|---|---|
| `STATE_VERSION` | `"operator_state.v46.1"` | Returned in every `get_operator_state` result |
| `HISTORY_MAX` | `200` | Hard cap on `elins.*` and `g_runs.*` entries per user per namespace |
| `TOPIC_MAX_LEN` | `200` | Char ceiling on `topic` field |
| `PREFERRED_DECAY` | `0.9` | Exponential decay factor applied on every `record_*` |
| `PREFERRED_INCREMENT` | `1.0` | Weight added to the bumped key |
| `VALID_SIGNAL_MODES` | `("cloud_only", "cloud_perplexity")` | ESO mode allow-list (re-exported by kernel) |

---

## 3. State shape and field semantics

`get_operator_state(user_id)` returns a 13-field dict in
dict-insertion order:

| Field | Type | Semantics |
|---|---|---|
| `user_id` | `str` | The user this state belongs to |
| `created_ts` | `float` | UTC timestamp of first state initialization (lazy on first `get_operator_state`) |
| `last_active_ts` | `float` | UTC timestamp of most recent write path; touched by every typed setter |
| `external_signal_mode` | `str` | One of `VALID_SIGNAL_MODES`; falls back to `"cloud_only"` on invalid stored value |
| `preferred_domains` | `dict[str, float]` | Domain → weight; decay+bump weighted preferences |
| `preferred_regions` | `dict[str, float]` | Region code → weight; decay+bump weighted preferences |
| `preferred_model` | `Optional[str]` | User-selected model id (validated against `model_router.SUPPORTED_MODELS`); `None` when cleared |
| `last_model_used` | `Optional[str]` | Most-recently-routed model id; updated by `record_model_used` |
| `local_model_usage_count` | `int` | Count of times the local model was selected; bumped by `bump_local_model_usage` |
| `el_ins_per_turn` | `bool` | v69 per-turn EL/INS analysis opt-in; default `False` |
| `elins_history` | `list[dict]` | Oldest→newest, capped at `HISTORY_MAX = 200`. Each entry: `{ts, elins_id, topic, region, kind}` |
| `g_history` | `list[dict]` | Oldest→newest, capped at `HISTORY_MAX`. Each entry: `{ts, g_id, mode, topic}` |
| `version` | `str` | Always `STATE_VERSION` |

### Field defaults (`_OS_FIELDS_DEFAULTS` — informational only)

```python
_OS_FIELDS_DEFAULTS: dict = {
    "created_ts":              None,    # populated lazily on first read
    "last_active_ts":          None,
    "external_signal_mode":    "cloud_only",
    "preferred_domains":       {},
    "preferred_regions":       {},
    "preferred_model":         None,
    "last_model_used":         None,
    "local_model_usage_count": 0,
    "el_ins_per_turn":         False,
}
```

Defined as a constant but **never iterated** — `get_operator_state`
reads each field explicitly with inline defaults. PASS‑4 FIX‑L3
removes the dead constant.

---

## 4. Preference decay and bumping

### `_decay_and_bump(weights, key) -> dict` (line 145)

Pure dict→dict transformation. Applied to `preferred_domains` and
`preferred_regions` on every `record_elins_interaction`; to
`preferred_domains` only on `record_g_run`.

```python
def _decay_and_bump(weights: dict, key: Optional[str]) -> dict:
    out: dict = {}
    for k, v in (weights or {}).items():
        try:
            new_v = float(v) * PREFERRED_DECAY        # = 0.9
        except (TypeError, ValueError):
            continue
        if new_v >= 0.001:                            # floor
            out[str(k)] = round(new_v, 4)
    if key:
        out[str(key)] = round(out.get(str(key), 0.0) + PREFERRED_INCREMENT, 4)  # +1.0
    return out
```

**Algorithm:**

1. Multiply every existing weight by `PREFERRED_DECAY = 0.9`.
2. Drop entries whose decayed weight falls below the floor `0.001`
   (prevents accumulation of floor noise).
3. Round to 4 decimal places for float stability.
4. If `key` is provided, add `PREFERRED_INCREMENT = 1.0` to that
   key's weight (which may have just been decayed).

### Decay timing

| Trigger | Region decay+bump | Domain decay+bump |
|---|---|---|
| `record_elins_interaction(user_id, elins_id, context)` | ✅ (uses `context.region`) | ✅ (uses `context.domain`) |
| `record_g_run(user_id, g_id, context)` | ❌ | ✅ (uses `context.domain`) |

### Determinism

The function is **pure** — same input always yields the same output.
Same `(weights, key)` → byte-identical result (to 4 decimal places).
No I/O, no module state.

### Weight evolution example

Starting `preferred_domains = {"finance": 1.0, "tech": 0.5}`. Calling
`record_elins_interaction` with `context.domain = "finance"`:

1. Decay: `{"finance": 0.9, "tech": 0.45}`.
2. Bump `"finance"`: `{"finance": 1.9, "tech": 0.45}`.

Calling 10 more times with `context.domain = None` (no bump):

1. Cycle 1: `{"finance": 1.71, "tech": 0.405}`
2. Cycle 5: `{"finance": 1.119, "tech": 0.266}`
3. Cycle 10: `{"finance": 0.663, "tech": 0.157}`

A weight bumped to 1.0 once needs ~65 untouched cycles to fall below
the 0.001 floor and be pruned.

---

## 5. History handling

### ELINS history (`elins.*` namespace)

`record_elins_interaction(user_id, elins_id, context=None)` (line 393):

1. `_validate_user(user_id)` (raises `ValueError` if empty).
2. `_strip_forbidden(context or {})` — removes raw-text fields.
3. `get_operator_state(user_id)` — ensures init + reads current state.
4. Build entry dict:
   ```python
   {
       "ts":       _now(),
       "elins_id": str(elins_id or ""),
       "topic":    _trim_topic(ctx.get("topic")),
       "region":   ctx.get("region"),
       "kind":     ctx.get("kind") or ("regional" if ctx.get("region") else "global"),
   }
   ```
5. `memory_vault.vault_put(user_id, _make_history_key(_ELINS_PREFIX, ts), entry)`.
6. Decay/bump `preferred_regions` (using `ctx.region`).
7. Decay/bump `preferred_domains` (using `ctx.domain`).
8. `_touch_last_active(user_id)`.
9. `_prune_history(user_id, _ELINS_PREFIX)` — drops oldest beyond
   `HISTORY_MAX = 200`.

Returns updated state dict via `get_operator_state(user_id)`.

### #G run history (`g_runs.*` namespace)

`record_g_run(user_id, g_id, context=None)` (line 429):

Same pipeline as above, except:

- Entry dict shape: `{"ts", "g_id", "mode", "topic"}`.
- Only `preferred_domains` decay/bump (no region).
- Vault key uses `_GRUNS_PREFIX`.

### `HISTORY_MAX` cap

`_prune_history(user_id, prefix) -> None` (line 170):

```python
def _prune_history(user_id: str, prefix: str) -> None:
    all_entries = memory_vault.vault_list(user_id)
    keys = [k for k in all_entries if k.startswith(prefix)]
    if len(keys) <= HISTORY_MAX:
        return
    sorted_keys = sorted(
        keys,
        key=lambda k: float((all_entries.get(k) or {}).get("ts") or 0.0),
    )
    excess = len(keys) - HISTORY_MAX
    for k in sorted_keys[:excess]:
        memory_vault.vault_delete(user_id, k)
```

**Algorithm:**

1. Read all vault entries for the user.
2. Filter to keys with the matching prefix.
3. If count ≤ 200, return (no-op).
4. Sort by `ts` (oldest first).
5. `vault_delete` the oldest excess entries until count = 200.

### History key format

`_make_history_key(prefix, ts) -> str` (line 125):

```python
def _make_history_key(prefix: str, ts: float) -> str:
    seq = _next_seq(prefix)
    return f"{prefix}{int(ts * 1000)}_{seq:06d}"
```

**Format:** `"{prefix}{ts_ms}_{seq:06d}"`. Two key invariants:

- **Chronological sort order:** the `ts_ms` portion is fixed-width
  enough (13 digits for current dates) that lexicographic sort
  matches chronological sort within a namespace.
- **Uniqueness within the same millisecond:** the zero-padded
  `_{seq:06d}` suffix from a process-wide counter (under `_SEQ_LOCK`)
  guarantees uniqueness even when two writes happen in the same
  millisecond.

`_list_history(all_entries, prefix)` (line 162) returns entries
sorted oldest→newest, capped at `HISTORY_MAX`.

### Cross-module read

The kernel never reads `elins_history` / `g_history` directly — only
through `get_operator_state` (full state) or `related_runs` (filtered
view). HTTP routes also use `get_operator_state` or the continuity
helpers.

---

## 6. Continuity helpers

### `related_runs(user_id, *, region=None, topic=None, limit=5) -> list[dict]` (line 458)

Newest-first matching of `elins_history` entries.

**Match rules:**

| Filter | Match condition |
|---|---|
| `region` given | `entry["region"] == region` |
| `topic` given | `topic.lower() in entry["topic"].lower()` (substring, case-insensitive) |
| Neither | Match every entry |

Returns up to `limit` matching entries, newest first.

### `continuity_section(user_id, *, last_topics_n=3) -> dict` (line 485)

Compact continuity snapshot:

```python
{
    "last_topics":          list of last N distinct topic strings (newest first),
    "preferred_domains":    [{"name": k, "weight": v}, ...top 5 by weight],
    "preferred_regions":    [{"name": k, "weight": v}, ...top 5 by weight],
    "external_signal_mode": str,
    "history_count":        len(elins_history),
    "g_count":              len(g_history),
}
```

Sort key for domains/regions: `(-weight, name)` (descending weight,
ascending name for ties). Top 5 retained.

### `continuity_context(user_id) -> dict` (line 508)

`continuity_section` + two additional fields:

```python
{
    **continuity_section(user_id),
    "last_region": str,       # most-recent region from elins_history (None if none)
    "user_id":     str,
}
```

### HTTP exposure

These functions are called from:

- **`/continuity/snapshot`** route in `app.py:8253` → `continuity_context`.
- **Dashboard / ELINSInspector** web routes → `related_runs`.

The functions themselves are pure — given a stable vault state, they
return the same dict. Real-world non-determinism comes from the vault
state changing (new records being persisted) between calls.

---

## 7. Vault mapping

### Vault key prefixes (3)

| Prefix | Purpose | Owner |
|---|---|---|
| `operator_state.` | Scalar/dict fields (one key per field) | This module |
| `elins.` | ELINS interaction history entries | This module |
| `g_runs.` | `#G` run history entries | This module |

All three are in `memory_vault.ALLOWED_NAMESPACES` (an 11-entry
allow-list). Any vault key whose leading segment is not in this set
is rejected by `memory_vault._validate_key`.

### Key layout

```
operator_state.created_ts                    → float
operator_state.last_active_ts                → float
operator_state.external_signal_mode          → str
operator_state.preferred_domains             → dict[str, float]
operator_state.preferred_regions             → dict[str, float]
operator_state.preferred_model               → str
operator_state.last_model_used               → str
operator_state.local_model_usage_count       → int
operator_state.el_ins_per_turn               → bool

elins.{ts_ms_a}_{seq:06d}                    → {ts, elins_id, topic, region, kind}
elins.{ts_ms_b}_{seq:06d}                    → {ts, elins_id, topic, region, kind}
...   (capped at 200)

g_runs.{ts_ms_a}_{seq:06d}                   → {ts, g_id, mode, topic}
g_runs.{ts_ms_b}_{seq:06d}                   → {ts, g_id, mode, topic}
...   (capped at 200)
```

Each scalar/dict field is a separate vault key. History entries are
individually keyed so a single `vault_delete` can prune the oldest
without rewriting the whole history.

### Migration path to memory_vault

`migrate_operator_state_to_vault(user_id, legacy_state) -> dict`
(line 526) is the **one-shot upgrade** from v45-style in-memory dicts
to v46 vault layout.

**Idempotent** — re-running overwrites scalar fields and recreates
history entries (since `_next_seq` allocates fresh suffixes).

Pipeline:

1. `_validate_user(user_id)` + `_validate(legacy_state is dict)`.
2. `memory_vault.vault_init(user_id)`.
3. For each scalar/dict field present in `legacy_state` and non-empty,
   write to `_OS_PREFIX + field_name`.
4. For each `elins_history` entry, `vault_put(_make_history_key(_ELINS_PREFIX, ts), entry)`.
5. For each `g_history` entry, `vault_put(_make_history_key(_GRUNS_PREFIX, ts), entry)`.
6. Return `get_operator_state(user_id)` (re-reads from vault).

**Deliberate non-application of `_strip_forbidden`** on legacy
history entries (documented at lines 137–138):

> *"`migrate_operator_state_to_vault` intentionally does NOT strip
> legacy history entries (one-shot upgrade path)."*

This is a documented privacy gap (PASS‑3B P2). Pre-v46 backends that
stored raw text in history land in v46 vault unchanged. PASS‑4 FIX‑H2
proposes an opt-in `scrub_legacy: bool = False` parameter.

---

## 8. Privacy boundaries

### `_strip_forbidden(ctx) -> dict` (line 133)

Removes 4 named fields from a metadata dict before persistence:

```python
def _strip_forbidden(ctx: dict) -> dict:
    out = dict(ctx or {})
    for forbidden in ("text", "scenario_text", "input_text", "raw_text"):
        out.pop(forbidden, None)
    return out
```

**Mirrors the v39 privacy contract** — operator_state never carries
prompt bodies, only metadata.

**Applied by:**

- `record_elins_interaction:402`
- `record_g_run:435`

**NOT applied by `migrate_operator_state_to_vault`** (line 137–138 —
deliberate).

### `_trim_topic(topic) -> str` (line 107)

Strip + truncate to `TOPIC_MAX_LEN = 200` chars:

```python
def _trim_topic(topic: Optional[str]) -> str:
    if not topic:
        return ""
    s = str(topic).strip()
    if len(s) > TOPIC_MAX_LEN:
        s = s[:TOPIC_MAX_LEN].rstrip()
    return s
```

Applied to the only free-form string field (`topic`) in every history
entry — both `record_elins_interaction:408` and `record_g_run:442`.

### Topic origin (caller invariant)

The kernel is responsible for building topic labels from analysis
output, never from raw user input:

- `intelligence_kernel.run_ELINS` builds `topic =
  synthesis.top_primitive · domain`.
- `intelligence_kernel.run_G` builds `topic = f"#G · pressure
  {round(pressure_meta, 3)}"`.

`operator_state` only enforces length (200 chars) — it does not
verify the topic is non-PII. The kernel-side discipline is the
primary defense; `_strip_forbidden` is the structural backstop for
the rest of the context dict.

### Privacy gap (PASS‑3B P1)

**The forbidden-fields blocklist is enumerated, not pattern-matched.**
Field names that would carry raw text but aren't in the 4-entry
blocklist pass through unstripped:

- `body`, `content`, `message`, `prompt`, `transcript`, `excerpt`,
  `snippet`, `passage`, `full_text`, `original_text`, `user_input`.

Privacy contract therefore depends on **caller discipline** (kernel
uses only the 4 known field names) + **blocklist completeness**.

PASS‑4 FIX‑H1 proposes adding suffix pattern-matching (`*_text`,
`*_body`, `*_content`, etc.) to close the gap. The 4-entry explicit
blocklist remains as a defense-in-depth fast path.

### Migration privacy

`migrate_operator_state_to_vault` deliberately preserves legacy data
un-stripped. **Pre-v46 backends with raw text in history land in v46
vault unchanged.** PASS‑4 FIX‑H2 proposes opt-in scrub mode.

### Logging discipline

The module defines `logger = logging.getLogger("clarityos.operator_state")`
at line 58 — but **never writes to it**. The module is silent from a
logging standpoint. Any operator-state-related log line comes from a
caller's logger (typically `clarityos.intelligence_kernel`).

---

## 9. Determinism and sequencing

### `_HISTORY_SEQ` counter

```python
_SEQ_LOCK = threading.Lock()
_HISTORY_SEQ: dict[str, int] = {}
```

Module-level dict keyed by namespace prefix. Each prefix maintains an
independent monotonic counter.

### `_next_seq(prefix) -> int` (line 116)

```python
def _next_seq(prefix: str) -> int:
    with _SEQ_LOCK:
        n = _HISTORY_SEQ.get(prefix, 0) + 1
        _HISTORY_SEQ[prefix] = n
        return n
```

Per-namespace, process-wide monotonic counter under `_SEQ_LOCK`. Two
writes in the same millisecond produce distinct vault keys via the
suffix.

### `_SEQ_LOCK`

`threading.Lock` allocated at module load (always-allocated — unlike
`intelligence_kernel._macro_seq_lock` which is lazy). No TOCTOU
window on first call. The critical section is intentionally short
(read-increment-write of one dict entry).

### Determinism guarantees

| Function | Determinism class |
|---|---|
| `_decay_and_bump(weights, key)` | Pure (with `round(..., 4)`) |
| `_trim_topic(topic)` | Pure |
| `_list_history(all_entries, prefix)` | Pure |
| `_strip_forbidden(ctx)` | Pure |
| `_make_history_key(prefix, ts)` | Deterministic given `(prefix, ts, seq)` — **wall-clock + counter** |
| `_next_seq(prefix)` | Deterministic within a process; not across processes |
| `get_operator_state(user_id)` | Deterministic given vault state |
| `related_runs(user_id, ...)` | Deterministic given vault state |
| `continuity_section(user_id, ...)` | Deterministic given vault state |
| `continuity_context(user_id)` | Deterministic given vault state |

### Non-deterministic surfaces

- **`_HISTORY_SEQ`** values are process-local. Two processes running
  simultaneously interleave seq numbers based on schedule. Within a
  single process the counter is strictly monotonic.
- **Wall-clock `ts`** in every history entry — `_now()` returns
  `time.time()`. Re-running a `record_*` call produces a different
  vault key (different `ts_ms` and `seq`).
- **`created_ts`** is set once on first `get_operator_state` call;
  subsequent reads return the same value. **Lazy initialization is
  not deterministic across first-call timing** but is stable per
  user once set.

### Test reset

`_reset_memory_for_tests()` (line 586) wipes the `_HISTORY_SEQ`
counter under `_SEQ_LOCK`:

```python
def _reset_memory_for_tests() -> None:
    global _HISTORY_SEQ
    with _SEQ_LOCK:
        _HISTORY_SEQ = {}
```

**Vault state is reset separately** — `memory_vault._reset_for_tests`
is the corresponding hook. `tests/conftest.py` invokes both.

---

## 10. Cross-module interactions

### `intelligence_kernel` interactions

The kernel is the **primary writer** to operator_state. Five write
paths:

| Kernel call site | operator_state function |
|---|---|
| `_resolve_model` (line 200) | `record_model_used(user, model_id)` |
| `_resolve_model` (line 207) | `bump_local_model_usage(user)` (when `model_id == LOCAL_MODEL_ID`) |
| `run_ELINS` (line 431) | `record_elins_interaction(user, record_id, context={topic, region, kind, domain})` |
| `run_regional_ELINS` | `record_elins_interaction(user, record_id, context={..., region: code})` |
| `run_G` (line 328) | `record_g_run(user, persisted_membership_id, context={mode, topic})` |

Plus `_apply_signal_mode_override` (kernel line 167) writes to
`operator_state.set_external_signal_mode` and `users_store.update_user`
(dual source of truth — PASS‑3B B2).

### Kernel read paths

| Kernel call site | operator_state function |
|---|---|
| `_resolve_external_signal_mode` (line 91) | `get_operator_state(user)` to read `external_signal_mode` field |
| `kernel_view_for_user` (line 1968) | `get_operator_state(user_id)` for `/me` embed |

### `model_router` interactions

**Read-only.** `model_router.select_model` step 3 (line 295–303)
lazy-imports `operator_state` and reads `preferred_model`:

```python
if user:
    try:
        import operator_state
        state = operator_state.get_operator_state(user) or {}
        pref = state.get("preferred_model")
        if isinstance(pref, str) and pref and pref != AUTO and is_valid_model(pref):
            return pref
    except Exception:
        pass
```

The router **never writes operator_state** — `intelligence_kernel._resolve_model`
is the writer for `last_model_used` and `local_model_usage_count`.

**Symmetric lazy-import cycle break:** `operator_state.set_preferred_model`
(line 351) lazy-imports `model_router` to call `is_valid_model`.

### `app.py` interactions

**Direct routes:**

| Route | operator_state function |
|---|---|
| `/me/operator_state` (GET, line 10373) | `get_operator_state(user)` |
| `/me/operator_state` (POST, line 10382) | `update_operator_state(user, patch)` |
| `/me/operator_state/model` (POST, line 10468) | `set_preferred_model(user, model_id)` |
| `/founder/operator/{user_id}/state` (GET, line 12380) | `get_operator_state(user_id)` |
| `/continuity/snapshot` (line 8253) | `continuity_context(user)` |

`app.py` never writes history entries directly — those go through
the kernel.

### Importers (22 total — 8 production + 14 tests)

- **Production:** `app.py`, `intelligence_kernel.py`, `model_router.py`
  (lazy), `runtime_intelligence_wiring.py`, `daily_personal_elins.py`,
  `founder_analytics.py`, `elins_dashboard.py`, `runtime_http.py` (via
  mounted router).
- **Tests:** `test_v39_operator_state.py` (primary),
  `test_v40_intelligence_kernel.py`, `test_v43_ux_and_analytics.py`,
  `test_v44_model_router.py`, `test_v45_local_model.py`,
  `test_v46_memory_vault.py`, `test_v47_threads.py`,
  `test_v79_regression_first_task.py`, `test_el_ins_*` (4 files),
  `test_runtime_intelligence_wiring.py`, `test_daily_personal_elins.py`,
  `tests/conftest.py`.

### Cycle break

| Cycle | Direction | Break |
|---|---|---|
| `operator_state ↔ model_router` | operator_state lazy → router; router lazy → operator_state | **Symmetric lazy import** |

Both sides lazy-import inside the function body — no top-level
coupling. PASS‑4 N1 mitigation proposes moving `SUPPORTED_MODELS` +
`is_valid_model` to a separate `model_constants.py` module to dissolve
the cycle entirely.

### No other coupling

- **No `app.py` import** — purely upstream.
- **No `intelligence_kernel` import** — purely downstream-called.
- **No `memory_vault` write outside its own API** — every persistence
  call uses the public vault API (`vault_init`, `vault_put`, `vault_get`,
  `vault_list`, `vault_delete`).

---

## 11. Known guarantees and gaps

### Strong runtime guarantees

1. **`user_id` validation at every entry** — empty/None → `ValueError`.
2. **ESO mode allow-list** — write rejects invalid; read falls back to
   `"cloud_only"`.
3. **Model id validation** — `set_preferred_model` rejects unknown
   ids via lazy `model_router.is_valid_model`.
4. **History caps** — 200 per namespace per user, enforced after
   every record_*.
5. **Topic length cap** — 200 chars via `_trim_topic`.
6. **Forbidden-field strip** — 4 raw-text fields removed before
   persistence.
7. **Vault key uniqueness** — `_next_seq` under `_SEQ_LOCK`
   guarantees distinct keys within the same millisecond.
8. **Chronological key sort** — `{prefix}{ts_ms}_{seq:06d}` format
   sorts lexicographically into chronological order.
9. **Decay+bump is pure** — same input always yields the same output.
10. **Weight floor pruning** — weights below 0.001 are dropped on
    every decay cycle.
11. **Selected ≡ recorded** — kernel writes `last_model_used` to
    operator_state for every model_router.select_model call.
12. **Single storage dep** — only `memory_vault` is imported eagerly.

### Known gaps

| Gap | Severity | Reference |
|---|---|---|
| **`_strip_forbidden` enumerated blocklist (4 fields)** — `body`, `content`, `message`, `prompt`, etc. pass through unstripped | High | PASS‑3B P1 / PASS‑4 FIX‑H1 |
| **Migration preserves un-stripped legacy entries** — `migrate_operator_state_to_vault` deliberately doesn't scrub | High | PASS‑3B P2 / PASS‑4 FIX‑H2 |
| **`_OS_FIELDS_DEFAULTS` is dead code** — defined but never iterated | Low | PASS‑4 FIX‑L3 |
| **`update_operator_state` unknown keys silently dropped** | Documented design | PASS‑3A I15 |
| **ESO mode dual source of truth** — kernel writes operator_state AND users_store | Medium — see kernel docs | PASS‑3B B2 |
| **No `try/except` around `memory_vault.*` calls** — vault failures propagate unchanged; no retry, no degradation | Documented design | PASS‑3A failure handling |
| **`logger` defined but never used** | Cosmetic | Source |

### Critical hardening targets (from PASS‑4)

| Fix | Target |
|---|---|
| **FIX‑H1** | `_strip_forbidden` add suffix pattern-matching for `*_text`, `*_body`, `*_content`, `*_message`, `*_prompt`, `*_transcript`, etc. Retain explicit 4-entry list as fast path. |
| **FIX‑H2** | `migrate_operator_state_to_vault` add `scrub_legacy: bool = False` parameter; when True, apply `_strip_forbidden` + `_trim_topic` to every legacy entry. |
| **FIX‑L3** | Remove unused `_OS_FIELDS_DEFAULTS` constant. |
| **N1 mitigation** | Move `SUPPORTED_MODELS` + `is_valid_model` to `model_constants.py` so both router and operator_state can import eagerly. Dissolves the lazy import cycle. |

None of these gaps are blocking. Core invariants — validation,
history caps, decay+bump, forbidden-field strip, vault key
uniqueness, namespace ownership — are intact.

---

## Summary

`operator_state.py` is the **per-user preference and history layer**
of the ClarityOS runtime. 592 lines, 12 public functions, 1 internal
locking primitive, 3 vault namespaces (`operator_state.*`, `elins.*`,
`g_runs.*`), 200-entry history caps, exponential preference decay
(`0.9`) with a 0.001 floor.

It owns **no HTTP routes** (those live in `app.py`), **no model
selection** (that lives in `model_router`), and **no encryption**
(that lives in `memory_vault`). It is purely a typed-state wrapper
over the vault with privacy hygiene and history bookkeeping.

The module is **production-current** (`STATE_VERSION =
"operator_state.v46.1"`) and is the third-most-imported runtime
module after `memory_vault` and `model_router`. The kernel writes;
the router reads (lazily); the HTTP layer calls direct typed
setters/getters.
