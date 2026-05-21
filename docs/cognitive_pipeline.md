# Cognitive Pipeline

## Overview

ClarityOS has **no single "cognitive pipeline" module** and no five-layer
`Orientation → Interpretation → Inversion → Integration → Transformation`
pipeline. That model was a design-canon construct with no implementation
counterpart.

What exists instead is a **layered runtime stack** — a sequence of
Unit-numbered modules that process one operator step from intent to response.
This document specifies that real stack.

## The operator-step runtime stack

A single operator step runs through the following modules, bottom to top. Each
has a locked output shape.

### `run_elins_session` — Unit 33 (`elins_session_integrator.py`)

ELINS session evaluation. Given a session context and ELINS inputs, it produces
the ELINS block (fusion, trajectory, cumulative risk, tags, and a vault
update).

### `apply_elins_runtime_actions` — Unit 34 (`elins_runtime_actions.py`)

Takes the ELINS block and a runtime context and produces a runtime action — a
`decision` and a list of `runtime_events`.

### `run_runtime_step` — Unit 35 (`runtime_kernel.py`)

The runtime kernel: the pure, deterministic per-step function — no model calls,
no persistence, no network. It:

1. Validates the operator intent and session context.
2. Resolves the ELINS sub-state from `vault_state.elins`.
3. Builds the Unit 33 session context and calls `run_elins_session`.
4. Builds the Unit 34 runtime context and calls `apply_elins_runtime_actions`.
5. Merges the vault state — replacing the `elins` sub-state, preserving the
   rest.
6. Builds a deterministic operator view (`headline` plus a safe `details`
   subset).

Its locked output carries `runtime_decision` (`allow` / `warn` / `block`),
`runtime_events`, the `elins_block`, the `vault_update`, and the
`operator_view`. Intent types are `query` / `action` / `plan` / `diagnostic`;
runtime modes are `normal` / `strict` / `diagnostic`.

### `dispatch_operator_intent` — Unit 36 (`runtime_dispatcher.py`)

The dispatcher. It wraps the runtime kernel and resolves the engine, the kernel
surface, and a `model_route`.

### `route_model_request` — Unit 38 (`model_router.py`)

The model call — routes the request to a provider and returns the model result
(`model_id`, response, metadata).

### `run_operator_session_step` — Unit 39 (`operator_session_runner.py`)

The top of the runtime stack. It composes Unit 36 (dispatch) and Unit 38 (the
model call) into one operator step, returning `{session_id, operator_id,
timestamp, runtime, model, vault_update}`.

### `session_loop.py` — Unit 40

The session-loop façade above Unit 39; it manages `session_state` and history.
The FastAPI endpoints `/operator/session/{start,step}` drive this stack, and
the `/session` web route is its operator UI (see `docs/runtime_ui.md`).

## Other reasoning components

Reasoning in ClarityOS is not confined to the runtime stack:

- **ELINS-canonical** (`ELINS/standard_elins.py`) — the deterministic
  scenario-analysis pipeline, invoked through `intelligence_kernel.run_ELINS`.
  Specified in `docs/elins/elins_deep_spec.md`.
- **The intelligence kernel** (`intelligence_kernel.py`) — unifies `#c`, `#G`,
  ELINS, regional and macro ELINS, and external signals behind its `run_*`
  functions.
- **The Regression-First protocol** (`problem_solver/regression_first.py`) — a
  layered diagnostic walk over a failing logic chain.

These are distinct flows. No single construct unifies them, and the
documentation should not imply one.

## What the Cognitive Pipeline is not

The five-layer pipeline (`Orientation`, `Interpretation`, `Inversion`,
`Integration`, `Transformation`), its per-layer "completion conditions" and
"transition statements," its cross-layer operators, and the
`Input → Processing → Curvature → Drift → Output` variant exist in no code. The
five `docs/layers/*.md` files that documented those layers have been removed.
