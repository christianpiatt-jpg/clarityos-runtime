# Continuity

## Purpose

Continuity is the runtime reentry subsystem. It reconstructs an operator's
session from persisted `vault_state` so the runtime kernel can resume long-arc
ELINS intelligence across cold starts — the OS's "resume where you left off"
layer. It is a pure, deterministic transform: given a `(session_id,
operator_id, vault_state)` tuple it returns the continuity object the kernel
needs to seed its next step, with no I/O of its own.

**Status:** `runtime_continuity.py` is implemented and fully tested but is
**not yet wired** — no production code path calls it (see Integration points).

## Implementation location

Repo-root module `runtime_continuity.py` (labelled "Unit 37" — the first
continuity-level module, designed to sit below the runtime kernel (Unit 35)
and the dispatcher (Unit 36)). Tests are in `tests/test_runtime_continuity.py`.
The module imports nothing — it is a pure leaf — and consumes, but does not
define, the `vault_state` schema (see Data model). (The two `_scratch/` files
named `continuity_*` are experimental scratch, not part of the runtime.)

## Data model

`resume_runtime_session(session_id, operator_id, vault_state)` consumes a
`vault_state` dict — or `None` on a cold start — and reads four fields:
`vault_state.elins.last_fusion`, `vault_state.elins.last_long_arc`,
`vault_state.elins.fusion_history`, and `vault_state.runtime_mode` (one of
`normal` / `strict` / `diagnostic`).

It returns a locked-shape continuity object: `{session_id, operator_id,
timestamp, continuity: {elins: {last_fusion (dict | None), last_long_arc
(dict | None), fusion_history (list)}, runtime_mode}}`. `timestamp` is resolved
deterministically — `last_fusion.timestamp`, else `last_long_arc.timestamp`,
else `""`. `fusion_history` is copied, so mutating the returned list never
affects the caller's `vault_state`.

## APIs / entrypoints

- `resume_runtime_session(session_id, operator_id, vault_state) -> dict` — the
  module's single public function; reconstructs the continuity object from
  `vault_state`. Raises `ValueError` on a malformed `session_id`,
  `operator_id`, or `vault_state`.

There are no HTTP endpoints. (`GET /continuity/snapshot` is an unrelated v28
surface — see Non-goals.)

## Integration points

- **There are currently no production call-sites.** `resume_runtime_session`
  is invoked only by `tests/test_runtime_continuity.py`; no production module
  imports `runtime_continuity`.
- **Intended caller** — the module is designed to seed the runtime kernel
  (Unit 35): its output is the continuity object the kernel would use for its
  next `run_runtime_step`. That wiring is not yet in the codebase.
- **Shared `vault_state` contract — not a call path** — `session_loop.py`
  persists `vault_state` (the long-lived per-operator ELINS state) and
  `elins_session_integrator.py` reads `vault_state.fusion_history` directly.
  Continuity consumes the same `vault_state.elins.*` shape, so the three agree
  on a data contract — but neither module calls `runtime_continuity`.

## Invariants

- **Pure and deterministic** — the same inputs produce a byte-equal output: no
  I/O, no network, no randomness, no model calls, no mutation of the inputs.
- **Locked output shape** — the returned object always carries exactly the
  keys shown in Data model, regardless of input.
- **Cold-start tolerant** — `vault_state` of `None`, `{}`, or a dict with no
  `elins` sub-state all yield a well-formed object with `None` / `[]`
  continuity fields.
- **Tolerant of malformed vault state** — an invalid `runtime_mode` falls back
  to `normal`; a malformed `last_fusion` / `last_long_arc` / `fusion_history`
  is treated as absent rather than raising.
- **Raises only on bad identifiers** — the sole error path is `ValueError`,
  for a non-string or empty `session_id` / `operator_id`, or a `vault_state`
  that is neither a dict nor `None`.

## Non-goals

- Continuity is not `GET /continuity/snapshot` — that is a separate v28
  cockpit metadata surface over `envelopes_store`, unrelated to this module.
- It is not the operator-state continuity slice — `operator_state.py`'s
  `continuity_section` / `continuity_context` are a v39 per-user metadata
  feature, also unrelated.
- It is not an LLM memory engine, a cross-session identity system, a
  scheduler, or a DEWEY or Markov subsystem.
- It persists nothing — writing and reading `vault_state` belongs to the vault
  and `session_loop.py` layers.

## Fiction removed

The 10g instruction flagged several constructs as possibly fictional; none are
in the code. `runtime_continuity.py` is **not** a "continuity vault as LLM
memory" (it makes no model calls and stores nothing), **not** a "cross-session
agent identity" system (it carries an `operator_id` and ELINS sub-state, not an
identity model), and **not** an "autonomous continuity engine" (it is a single
pure function — no engine, no loop, no background task, no scheduler). It
carries no DEWEY or Markov semantics. The instruction also named
`session_loop.py` and `elins_session_integrator.py` as call sites; they are
not — they share the `vault_state` data contract but never invoke
`runtime_continuity` (see Integration points).
