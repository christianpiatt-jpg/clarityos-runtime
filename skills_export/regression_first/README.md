# ProblemSolver.REGRESSION_FIRST — EL/INS + Regression-First Integration

**Status:** v1.0 — canonical external bundle.

The cognitive-signal pipeline for ClarityOS operator-facing reasoning.
Every operator message is run through EL/INS analysis; problem
reports auto-trigger Regression-First Protocol and emit a layered
diagnostic chain. The model emits ONE unified JSON packet — no prose.

## Files

| File                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `system_prompt.md`  | Canonical instruction set. The full system prompt an LLM uses when it operates as the EL/INS + Regression-First analyzer. |
| `schema.json`       | JSON Schema (Draft 07) for the **emitted packet**. What Claude returns on every operator message. |
| `README.md`         | This file.                                           |

## Two shapes, one source of truth

There are **two** related shapes in this protocol:

1. **Emitted packet** (`schema.json`, this bundle) — what the LLM
   returns. Includes EL/INS scoring, signals, classification,
   operator intent, `regression_required` flag, a stateless
   `regression_chain` skeleton (layer/name/question/location/goal),
   and a `recommended_system_action`.
2. **Stored chain** (kernel internal, see `problem_solver/`) — the
   stateful envelope ClarityOS persists. Wraps the emitted chain
   skeleton with `chain_id`, `protocol`, `problem`, `source`,
   `created_ts`, per-layer `status` + `notes`, chain `state`, and
   a root-cause `summary`. The kernel maps the emitted `location`
   field to the stored `where` field.

The emitted packet is the contract with the model. The stored chain
is the contract with the OS. Both are versioned together.

## Intended consumers

This bundle is the **canonical external spec**. Anyone (Claude API,
Langbridg, third-party LLMs) can adopt it directly without touching
ClarityOS:

1. Load `system_prompt.md` as the system prompt for the model.
2. Send the operator's message as the user message.
3. Parse the model response against `schema.json` (emitted packet).
4. If `regression_required` is true, route the `regression_chain`
   into whatever stateful walk the consumer prefers.

## Default chain template

When `regression_required` is true, the prompt recommends a six-layer
walk:

| Layer | Name                  | What it answers                                       |
|-------|-----------------------|-------------------------------------------------------|
| 1     | Domain & Routing      | Is the request reaching the right surface at all?     |
| 2     | Template Layer        | Does the surface render the expected template?        |
| 3     | URL Mapping           | Does the routing table point at the right handler?    |
| 4     | Content Presence      | Is the content the handler reads actually present?    |
| 5     | Backend Wiring        | Did the underlying kernel/store contract hold?        |
| 6     | External Dependencies | Did outbound calls (model_router / oracle) honor SLA? |

LLM-driven mode may emit a custom chain tailored to the reported
problem — it must still match the emitted-packet schema.

## State machine (kernel side)

Once the kernel ingests the emitted packet and wraps each layer in
its stateful envelope, a chain moves through three states:

```
awaiting_verification ──► ready_for_root_cause ──► root_cause_identified
        (any layer            (every layer has        (summary block
         still pending)        a finding)              populated)
```

`summarize_root_cause` is gated: it MUST raise (or return a 400 from
an endpoint) while any layer is still `pending`.

## Relationship to the ClarityOS kernel module

ClarityOS ships a sibling **kernel module** (`problem_solver/`) that
uses the same prompt and schema for in-runtime packet generation,
plus a deterministic Python fallback for offline / phone runtime
paths. The kernel module loads `system_prompt.md` from this bundle
at import time — meaning **this file is the single source of truth**
for both the external skill and the internal runtime.

Per [`ARCHITECTURE.md`](../../ARCHITECTURE.md), ClarityOS runtime
modules MUST NOT import any other file from `/skills_export/`. The
problem_solver kernel module reads
`skills_export/regression_first/system_prompt.md` as plain text —
not as a Python import — which is allowed.

## Relationship to EL/INS bundle

This bundle is an **integration** of the EL/INS reasoning-stability
operator (`skills_export/el_ins/`) with the Regression-First protocol.
EL/INS lives standalone for analyses that don't need a regression
chain; this bundle wraps EL/INS analysis with a problem-detection
trigger so a single packet covers both responsibilities.

When a consumer only needs EL/INS, they should use the EL/INS bundle
directly. When a consumer wants the merged cognitive-signal pipeline,
they should use this one.

## Versioning

The bundle pins `version` in line with the broader `/skills_export/`
manifest at `/skills_export/manifest.json`. Breaking schema changes
require a major version bump and a parallel kernel update.

## License / use

Same license as ClarityOS. See repo root.
