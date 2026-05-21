# Regression-First Protocol

## Purpose

The Regression-First Protocol is a deterministic, operator-facing
chain-of-findings lifecycle with two-namespace vault persistence and
one parser entry point for LLM-emitted unified packets. The
subsystem itself makes no model calls; it provides the structured
store, the lifecycle operations, and the packet parser that consumes
output from an LLM running under the canonical
`skills_export/regression_first/` bundle prompt elsewhere in the
system.

A "chain" is an operator log of findings (one per chain layer) plus
free-form key/value tags and a title; chains stay open until
`close_chain` is called, at which point they are permanently
immutable. The protocol records what the operator submits; it does
not infer, advance, or auto-populate layers.

## Implementation location

- **Package:** `problem_solver/` (4 files; `__init__.py` re-exports
  the full public surface from the other three).
- **Source files:**
  - `problem_solver/regression_first.py` — chain lifecycle
    (start / record_finding / close / tag / delete_tag / archive /
    get / list), the `analyze_packet` JSON parser, and constants.
  - `problem_solver/chain_store.py` — `RegressionChainStoreProtocol`
    + two implementations (`InMemoryRegressionChainStore`,
    `VaultBackedRegressionChainStore`) + module-level `DEFAULT_STORE`.
  - `problem_solver/auto_trigger.py` — pure cue-lexicon detector
    (`should_auto_trigger`, `extract_problem`, `CUE_WORDS`,
    `CUE_PHRASES`).
  - `problem_solver/__init__.py` — defines `__all__` and re-exports
    the public surface.
- **External bundle** (plain-text resource, never imported as Python):
  - `skills_export/regression_first/system_prompt.md` — canonical LLM
    system prompt for upstream packet generation.
  - `skills_export/regression_first/schema.json` — unified packet
    shape.
  - `skills_export/regression_first/README.md` — manifest doc.
- **HTTP routes** — 10 endpoints in `app.py` (see §4).
- **Kernel integration** — `intelligence_kernel.run_regression_first`
  (v79; see §5 and `docs/intelligence_kernel.md`).
- **Imports** — the subsystem's complete dependency surface:
  - stdlib: `json`, `logging`, `re`, `time`, `uuid`, `pathlib`,
    `typing`.
  - `memory_vault` (only inside `chain_store.py`, for
    `VaultBackedRegressionChainStore`).

That is the entire dependency surface. No model SDKs are imported
anywhere under `problem_solver/`.

## Data model

### TypedDicts

```python
RegressionLayer{
    layer_index: int,         # 0-based, operator-supplied
    status:      str,         # one of LAYER_STATUSES
    notes:       Optional[str],
    updated_at:  int,         # ms epoch, set by kernel on every write
}

RegressionChain{
    chain_id:    str,         # canonical UUID4 string with dashes
    created_at:  int,         # ms epoch, set on start_chain
    closed_at:   Optional[int],  # ms epoch, set on close_chain
    title:       str,
    notes:       Optional[str],
    layers:      list[RegressionLayer],
    tags:        dict[str, str],
    archived:    bool,        # v81; orthogonal to closed_at
}

CognitivePacket(TypedDict, total=False){  # LLM-emitted; parsed by analyze_packet
    EL:                        int,            # 0..5
    INS:                       int,            # 0..5
    ratio:                     str,
    el_signals:                list[str],
    ins_signals:               list[str],
    classification:            str,            # one of CLASSIFICATIONS
    operator_intent:           str,
    regression_required:       bool,
    regression_chain:          list[dict],     # informational skeleton; NOT seeded as layers
    recommended_system_action: str,
    chain:                     Optional[RegressionChain],  # populated when build_chain=True
}
```

### Constants

```python
# problem_solver/regression_first.py
PROTOCOL_NAME       = "ProblemSolver.REGRESSION_FIRST"
LAYER_STATUSES      = ("ok", "issue", "blocked", "unknown")
CLASSIFICATIONS     = ("emotion-dominant", "balanced", "structure-dominant")
SYSTEM_PROMPT_PATH  = <repo>/skills_export/regression_first/system_prompt.md  # pathlib.Path
TITLE_MAX           = 200
NOTES_MAX           = 8192       # 8 KiB
LAYER_NOTES_MAX     = 4096       # 4 KiB
TAG_KEY_MAX         = 64
TAG_VALUE_MAX       = 256
TAGS_PER_CHAIN_MAX  = 32

# problem_solver/chain_store.py
VAULT_NAMESPACE     = "regression_chains"
DEFAULT_STORE       = InMemoryRegressionChainStore()   # module-level singleton

# problem_solver/auto_trigger.py
CUE_WORDS           = frozenset({...22 lowercase tokens...})
CUE_PHRASES         = (...11 lowercase multi-word phrases...)
```

### Vault namespaces

The protocol persists under **two** namespaces of `memory_vault`
(see `docs/memory_vault.md`):

- `regression_chains.{chain_id}` — chain documents (every save by
  `VaultBackedRegressionChainStore`).
- `regression_packets.{chain_id}` — write-once original packets
  (v80; consumed by `/replay` in v82).

Both appear in `memory_vault.ALLOWED_NAMESPACES`.

### Storage protocol

```python
@runtime_checkable
class RegressionChainStoreProtocol(Protocol):
    def get(self, chain_id: str) -> Optional[dict]: ...
    def save(self, chain: dict) -> None: ...
    def delete(self, chain_id: str) -> None: ...
    def list_all(self) -> list[dict]: ...
```

Two implementations ship:

| Implementation | Use | Backing | Ordering |
|---|---|---|---|
| `InMemoryRegressionChainStore` | tests, standalone callers, kernel default | process-local dict | strictly-monotonic insertion seq → newest-first |
| `VaultBackedRegressionChainStore(user_id)` | production / HTTP endpoint side | `memory_vault` under `regression_chains` namespace | `(created_at, chain_id) DESC` |

The kernel functions take `store=None` everywhere; when omitted they
use the module-level `DEFAULT_STORE`. HTTP endpoint handlers
construct a fresh `VaultBackedRegressionChainStore(session_user)` per
request — that is the only place per-user partitioning is bound.

## APIs / entrypoints

### Public functions (12)

**Chain lifecycle:**

- `start_chain(title: str, *, notes: Optional[str] = None, store=None) -> RegressionChain` —
  opens an empty chain (`layers=[]`, `tags={}`, `archived=False`,
  `closed_at=None`). Raises `ValueError` for empty/oversized title
  or oversized notes.
- `record_finding(chain_id: str, layer_index: int, status: Literal["ok","issue","blocked","unknown"], notes: Optional[str] = None, *, store=None) -> RegressionChain` —
  records an operator finding for `layer_index`. Layers auto-grow:
  if no entry exists for that index, a new layer is appended and
  the list re-sorted ascending by `layer_index`; if one exists,
  status/notes/updated_at are overwritten. Raises `KeyError` on
  unknown chain, `ValueError` on bad status / negative or non-int
  `layer_index` / oversized notes / chain already closed.
- `close_chain(chain_id: str, *, notes: Optional[str] = None, store=None) -> RegressionChain` —
  sets `closed_at` to now and optionally overwrites the chain's
  top-level notes. Irreversible; raises `ValueError` on double-close.
- `tag_chain(chain_id: str, tags: dict, *, store=None) -> RegressionChain` —
  merges `tags` into the chain's tag dict; existing keys overwritten,
  unmentioned keys preserved. Validates types + sizes +
  `TAGS_PER_CHAIN_MAX` before mutating (atomic). Empty dict is a
  no-op. Raises on closed chain.
- `delete_tag(chain_id: str, key: str, *, store=None) -> RegressionChain` —
  removes one tag key. No-op when absent. v81. Raises on closed
  chain.
- `archive_chain(chain_id: str, *, store=None) -> RegressionChain` —
  sets `archived = True`. Idempotent and one-way (no `unarchive`
  surface). Does NOT close the chain and does NOT lock further
  mutations. v81.
- `get_chain(chain_id: str, *, store=None) -> RegressionChain` —
  raises `KeyError` if absent.
- `list_chains(*, store=None) -> list[RegressionChain]` —
  newest-first per the store's ordering policy.

**Packet parser:**

- `analyze_packet(raw: Union[str, dict], *, title: Optional[str] = None, build_chain: bool = True, store=None) -> Optional[CognitivePacket]` —
  **pure deterministic JSON parser + validator.** Strips a single
  Markdown fence if present, `json.loads` the payload, validates
  required fields, `EL`/`INS` int + range `0..5`, and
  `classification ∈ CLASSIFICATIONS`. Returns `None` on any parse
  or validation failure (never raises). When `build_chain=True AND
  regression_required=True AND effective title is non-empty`, calls
  `start_chain` and embeds the new chain at `packet["chain"]`.
  **No LLM call. No prompt usage. No I/O beyond the optional
  `start_chain` write through the supplied `store`.**

**Auto-trigger (pure detection, no side effects):**

- `should_auto_trigger(text: str, *, el_ins_result: Optional[dict] = None) -> bool` —
  returns `True` iff `text` contains a cue word or cue phrase AND
  (when `el_ins_result` is supplied) the upstream EL/INS
  `ratio_classification == "high_el"`. With `el_ins_result=None`,
  a cue match alone is sufficient.
- `extract_problem(text: str) -> str` — strips and collapses
  whitespace; returns the empty string for empty/whitespace input
  (never returns `None`).

### HTTP entrypoints (10)

All under `/me/regression_first/`; handlers in `app.py`. Each
endpoint constructs a fresh `VaultBackedRegressionChainStore(session_user)`
and passes it through to the corresponding kernel function:

| Method | Path | Handler | File:Line | Version |
|---|---|---|---|---|
| POST | `/me/regression_first/start` | `me_regression_first_start` | app.py:11461 | v76 |
| POST | `/me/regression_first/step` | `me_regression_first_step` | app.py:11497 | v76 (calls `record_finding`) |
| GET | `/me/regression_first/{chain_id}` | `me_regression_first_get` | app.py:11544 | v76 |
| GET | `/me/regression_first` | `me_regression_first_list` | app.py:11563 | v76 |
| POST | `/me/regression_first/{chain_id}/close` | `me_regression_first_close` | app.py:11589 | v76 |
| POST | `/me/regression_first/{chain_id}/tag` | `me_regression_first_tag` | app.py:11627 | v76 |
| POST | `/me/regression_first/delete_tag` | `me_regression_first_delete_tag` | app.py:11673 | v81 |
| POST | `/me/regression_first/archive` | `me_regression_first_archive` | app.py:11698 | v81 |
| POST | `/me/regression_first/packet` | `me_regression_first_packet` | app.py:11779 | v80 |
| POST | `/me/regression_first/replay` | `me_regression_first_replay` | app.py:11950 | v82 |

## Integration points

### Intelligence Kernel (v79)

`intelligence_kernel.run_regression_first(packet, *, user_id=None, model_id=None, store=None) -> dict`
(intelligence_kernel.py:1256; see `docs/intelligence_kernel.md` 10q
section). Behaviour:

- Calls `_resolve_model(user_id, task="regression_first", override=model_id)` —
  **telemetry only.** The resolved model id is recorded on
  `operator_state.last_model_used` (per `_resolve_model` contract)
  and embedded in the `kernel_run` log meta. The kernel does **not**
  invoke a model.
- Calls `problem_solver.analyze_packet(packet, store=store)` — the
  only call into the subsystem.
- Emits `kernel_logging.log_kernel_run(kind="run_regression_first",
  ..., meta={model_id, chain_id, regression_required,
  classification})`.
- The kernel docstring at intelligence_kernel.py:1239-1242 states
  explicitly that the kernel does **not** drive an LLM call here:
  packets are emitted upstream under the canonical bundle prompt.

### Model router

`model_router.TASK_DEFAULTS["regression_first"] = "openai:gpt-4o"`
(model_router.py:131). The comment on that line references Claude
3.7 (the model the bundle prompt was originally written for); the
entry value does not match the comment. This document records the
code-truth (`openai:gpt-4o`) and does **not** normalize the
discrepancy — the mismatch is preserved here for future review.

### Memory Vault

The protocol consumes `memory_vault` only via
`VaultBackedRegressionChainStore`. Functions used:

- `vault_get(user_id, key, default=None)` — chain reads.
- `vault_put(user_id, key, value)` — chain saves.
- `vault_delete(user_id, key)` — chain deletes.
- `vault_keys_for_user(user_id)` — `list_all` scans.

Chains are stored under `regression_chains.{chain_id}` keys. A v82
path additionally writes original packets under
`regression_packets.{chain_id}` (write-once; consumed by `/replay`).
See `docs/memory_vault.md` for the substrate; 10l registered both
namespaces in `memory_vault.ALLOWED_NAMESPACES`.

### Skills export bundle

The `skills_export/regression_first/` directory contains the
canonical LLM-side artifacts. `regression_first.py:151` reads
`system_prompt.md` as plain text via `SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")`
and caches it in `_PROMPT_CACHE`. The bundle is **never imported as
Python**, per the no-skills-import architecture boundary. The
prompt loader is available for upstream callers to use when
constructing LLM requests; nothing in the subsystem invokes any
model.

### Tests

The behavioural contract is pinned by ~152 tests across 6 files in
`tests/`:

| File | Approx tests | Coverage |
|---|---|---|
| `test_v79_regression_first_task.py` | 22 | Kernel task dispatch, model resolution, graceful degrade |
| `test_v80_regression_first_packet.py` | 22 | `POST /packet`, chain creation, per-user vault partition |
| `test_v81_regression_first_archive.py` | 35 | Archive flag, `delete_tag`, backward compat for pre-v81 chains |
| `test_v82_regression_first_replay.py` | 17 | Replay endpoint, original packet reload, timeline continuity |
| `test_regression_first_endpoints.py` | 27 | Full HTTP surface; manifest locks; model resolution |
| `test_regression_first_vault_timeline.py` | 29 | Vault persistence + event timeline across versions |

## Invariants

- **Pure deterministic subsystem.** Every public function in
  `problem_solver/` is deterministic: same inputs → byte-equal
  outputs. The LLM-mediation step is **upstream** of `analyze_packet`,
  in whatever caller constructs the unified packet under the bundle
  prompt.
- **No model invocation inside the subsystem.** No module under
  `problem_solver/` imports `openai`, `anthropic`, or calls
  `model_router.route_request` / `route_model_request`. The system
  prompt is loaded as plain text for upstream callers; nothing in
  the subsystem sends a model request.
- **Closing is irreversible.** `record_finding`, `tag_chain`,
  `delete_tag`, and `close_chain` all raise `ValueError` once
  `chain["closed_at"]` is set.
- **Archive is orthogonal to close.** A chain can be open+archived
  or closed+archived. `archive_chain` does NOT close the chain and
  does NOT lock further mutations.
- **Archive is idempotent and one-way.** No `unarchive` surface;
  calling on an already-archived chain returns the chain unchanged.
- **Layers auto-grow and re-sort.** `record_finding` either updates
  an existing layer at `layer_index` or appends and re-sorts the
  list ascending by `layer_index`.
- **Chain IDs are canonical UUID4 strings** with dashes
  (`uuid.uuid4()` via `_make_chain_id`).
- **No canonical pre-populated layer scaffold.** `start_chain`
  creates an empty layer list. The packet's `regression_chain`
  skeleton (when present in the LLM output) is **informational**;
  the subsystem does not seed it as layers. The operator drives
  layer creation via `record_finding`.
- **Validation gates on packet parse:** required-field check, `EL`
  / `INS` int + range `0..5`, `classification ∈ CLASSIFICATIONS`.
  Any failure returns `None` from `analyze_packet` — never raises.
- **Conditional chain build inside `analyze_packet`:** opens a
  chain only when `build_chain=True AND regression_required=True
  AND effective_title is non-empty`. Otherwise returns the packet
  with `chain=None`.
- **Per-user vault partitioning is structural.**
  `VaultBackedRegressionChainStore(user_id)` is bound at
  construction; cross-user reads are structurally impossible because
  `vault_get` is partitioned per-user.
- **V81 backward-compat read.** `_coerce_chain_defaults` injects
  `archived=False` for pre-v81 vault entries on read.
- **In-memory store insertion-seq tiebreak.** Same-millisecond
  `start_chain` calls sort deterministically newest-first via a
  process-wide monotonic counter.
- **Vault store sorts `(created_at, chain_id) DESC`.** No insertion
  counter survives restart; ms-collisions resolve lexicographically
  by UUID.
- **System prompt cache is lazy + sticky.** Loaded once on first
  `_load_system_prompt()` call; `_reset_prompt_cache()` is the test
  hook.
- **Auto-trigger is pure.** No I/O, no model imports.
  `should_auto_trigger` is a cue-presence test (with optional
  EL/INS gating); `extract_problem` is whitespace normalisation.
- **Kernel model resolution is telemetry-only.**
  `intelligence_kernel.run_regression_first` resolves a `model_id`
  to record on `operator_state.last_model_used`, but never invokes
  a model.
- **Tags are bounded and validated atomically.** Keys ≤
  `TAG_KEY_MAX`, values ≤ `TAG_VALUE_MAX`, total tags ≤
  `TAGS_PER_CHAIN_MAX`. Validation happens before any mutation so a
  partial failure leaves no state behind.
- **Empty-notes normalisation.** `_coerce_optional_notes`
  normalises whitespace-only strings to `None`, so callers don't
  have to distinguish "I sent nothing" from "I sent an empty
  string".

## Non-goals

The Regression-First Protocol is **not**:

- a generalized reasoning engine — it is a structured lifecycle
  around findings;
- an LLM caller — no module under `problem_solver/` ever invokes a
  model;
- a multi-mode kernel task — there is exactly one entry into the
  subsystem from the kernel (`analyze_packet` via
  `run_regression_first`);
- an autonomous decision system — every operation is request-driven;
  chains never advance on their own;
- a state machine — there is no canonical layer scaffold and no
  automatic progression between layers or statuses;
- a general-purpose tagging surface — tags are merge-on-write
  key/value strings with bounded count and size; no relational
  queries, no filtering, no bulk replace;
- a search engine — `list_chains` returns all chains newest-first;
  there is no `find_by_*` and no query language;
- a skill-manifest consumer — the `skills_export/regression_first/`
  bundle is read as plain text, never imported as Python;
- coupled to the ELINS-regression analytics suite
  (`elins_regression_*.py`) — that is a separate subsystem, scoring
  engines over scenario timelines, documented in
  `docs/elins/elins_deep_spec.md` (10o). The shared word
  "regression" is a namespace collision, not an architectural link;
- a cross-user chain registry — `VaultBackedRegressionChainStore(user_id)`
  is per-user-bound; cross-user reads are structurally impossible;
- a software-testing regression framework — "regression" here refers
  to operator findings during a diagnostic walk, not test-suite
  results.

## Fiction removed

The following constructs are explicitly not present in
`problem_solver/*.py` and must not be inferred:

- **No state machine that advances chains automatically** — operators
  drive layer creation; the kernel never "advances" a chain
  (regression_first.py module docstring, lines 9-14).
- **No `reopen` / `unclose` surface** — closing is irreversible.
- **No `unarchive` surface** — archive is one-way
  (regression_first.py:484-485).
- **No kernel-driven LLM call** — `intelligence_kernel.run_regression_first`
  explicitly does NOT invoke a model (intelligence_kernel.py:1239-1242).
- **No skill-manifest Python import** — the bundle is read as plain
  text via `Path.read_text` (regression_first.py:151), never
  imported.
- **No LLM call inside `analyze_packet`** — the function is pure
  deterministic JSON parsing and validation; the LLM mediation
  happens UPSTREAM, in the caller that constructs the packet under
  the bundle prompt.
- **No LLM call inside the auto-trigger layer** —
  `should_auto_trigger` and `extract_problem` are
  pure-lexicon / pure-string functions.
- **No cross-user chain access** — structurally precluded by
  per-user vault partitioning at `VaultBackedRegressionChainStore`
  construction.
- **No canonical pre-populated layer scaffold** — the packet's
  `regression_chain` skeleton is informational; layers are not
  seeded from it.
- **No background reconciliation, scheduler, or background worker**
  — every operation is request-driven; there is no module-level
  threading, asyncio, or timer.
- **No tag query / filter / bulk-replace surface** — `tag_chain`
  merges, `delete_tag` removes one key; no other tag operations
  exist.
- **No `find_by_*` or chain query language** — `list_chains` returns
  all chains newest-first; filtering is the caller's job.
- **No fabricated endpoint paths** — the protocol exposes exactly
  the 10 routes listed in §4. Endpoints named `/record`, `/get`,
  `/list` do not exist; the real paths are `/step`,
  `/{chain_id}`, and `/`.
- **No coupling to the ELINS-regression suite** —
  `elins_regression_single_party`, `elins_regression_economic_coercion`,
  and `elins_regression_compare` are a separate analytics subsystem
  documented in `docs/elins/elins_deep_spec.md` (10o). The shared
  word "regression" is a naming collision, not an architectural
  link.
- **No `CognitivePacket` persistence as a TypedDict shape** —
  `CognitivePacket` is the in-memory Python type used by
  `analyze_packet`'s return value; what gets stored under
  `regression_packets.{chain_id}` is the original raw packet dict
  preserved for replay, not a parsed `CognitivePacket` view.

Only the behaviour, signatures, integrations, and constants
described in this document are present in the code; the verified
surface is locked by ~152 tests across the 6 test files listed in §5.

## Appendix A — Regression-First test topology

This appendix describes the topology of the Regression-First test
suite: 151 tests across 6 files. It is intentionally structural, not
narrative — the goal is to show which versions, surfaces, and
invariant families are pinned where, not to restate individual
assertions.

### A.1 Files and dominant surfaces

| File | Version focus | Approx. test count | Dominant surfaces |
|---|---|---|---|
| `test_v79_regression_first_task.py` | v79 | ~22 | Kernel task (`run_regression_first`), model resolution, graceful degrade |
| `test_v80_regression_first_packet.py` | v80 | ~22 | `/packet` endpoint, packet parser, chain creation, per-user vault partitioning |
| `test_v81_regression_first_archive.py` | v81 | ~35 | Archive route, `archive_chain`, `delete_tag`, backward compat for pre-v81 chains |
| `test_v82_regression_first_replay.py` | v82 | ~17 | `/replay` endpoint, original packet reload, timeline continuity |
| `test_regression_first_endpoints.py` | v76–v82 | ~27 | Full HTTP surface, auth/session, endpoint registration, manifest/version locks |
| `test_regression_first_vault_timeline.py` | v76–v82 | ~28 | Vault persistence, per-user partitioning, event timeline across versions |

Counts are approximate; the exact total is 151 tests across all six
files.

### A.2 Invariant families → test coverage

This matrix shows which files primarily pin each invariant family.
Many invariants are covered in more than one place; this table lists
the dominant locations.

| Invariant family | Representative coverage |
|---|---|
| **Auth / session binding** | `test_regression_first_endpoints.py` (all routes require a logged-in user; no cross-user access) |
| **Per-user partitioning** | `test_v80_regression_first_packet.py`, `test_regression_first_vault_timeline.py` (chains and packets are structurally per-user) |
| **Determinism / graceful degrade** | `test_v79_regression_first_task.py` (kernel task determinism, `analyze_packet` returning `None` on parse failure) |
| **Endpoint registration / manifest lock** | `test_regression_first_endpoints.py` (routes, methods, and version tags are locked; health/version tests ensure no drift) |
| **Lifecycle mutation rules** | `test_v81_regression_first_archive.py` (close vs archive, tag merge/delete, irreversible close, one-way archive) |
| **Persistence / timeline** | `test_regression_first_vault_timeline.py` (vault writes, read-after-write, event ordering across v76–v82) |
| **Backward compatibility** | `test_v81_regression_first_archive.py`, `test_v82_regression_first_replay.py` (pre-v81 chains, v80 packets, v82 replay semantics) |
| **Packet parser behavior** | `test_v80_regression_first_packet.py` (valid/invalid payloads, `analyze_packet` validation gates, conditional chain creation) |
| **Replay semantics** | `test_v82_regression_first_replay.py` (original packet reload from `regression_packets.{chain_id}`, idempotent replay) |

### A.3 Duplicate names and health-lock tests

Two topology hazards are worth recording explicitly:

- **Class-qualified duplicates.** Some test function names are reused
  in different test classes (e.g., the same `test_*` name under two
  different `Test*` classes). For topology purposes, these are
  distinct nodes and should be treated as `ClassName::test_name`
  rather than collapsed by function name alone.

- **Repeated health/version-lock tests.** A small number of
  `test_health_version_locked`-style tests appear in more than one
  file to pin both endpoint registration and manifest/version
  invariants. They are intentionally duplicated; removing one copy
  weakens the lock on the corresponding surface.

This appendix is descriptive, not exhaustive: for exact test names
and class structures, refer directly to the six files listed in
§A.1. The purpose here is to make clear which parts of the
Regression-First Protocol are pinned where, so future changes can be
planned against a known test topology.
