# Runtime UI

## Overview

The Runtime UI is the set of operator-facing web surfaces over the server-side
runtime. The runtime itself — sessions, the per-step decision, the envelope,
and persistence — runs on the backend (`runtime_*.py`). The UI holds no runtime
state of its own; it starts sessions, submits steps, and renders the responses.

There is no four-pane process / log / diagnostics / CLI cockpit. The Runtime UI
is three surfaces: the **Session** route, the **Session History** route, and
the **Runtime Panel** embedded in the cockpit.

## Session route (`/session`)

`web/src/routes/Session.tsx` is the operator runtime surface; it runs one step
per submission.

- On mount it calls `startSession` (`/operator/session/start`), resuming a
  prior session if a session id is in `localStorage`, otherwise minting a new
  one. Server-side `runtime_persistence` holds state across requests; the
  browser keeps only the resume id.
- A submission calls `stepSession` (`/operator/session/step`) with the text and
  an **intent** — one of `query`, `action`, `plan`, `diagnostic`.
- Panels: `STATE` (`session_id`, `operator_id`, history step count); `COMPOSE`
  (text area, intent select, `SEND`); `RUNTIME RESPONSE`; `MODEL RESPONSE`.
- The runtime response (`step_result.runtime.ui_response`) carries a
  `severity` (the UI styles `critical` and `warning` distinctly; other values
  render as nominal), a `headline`, a `body`, and `tags`.
- The model response carries `model_id`, `provider`, a `mock` flag, and the
  response `text`.
- `NEW SESSION` discards the resume id and mints a fresh session.

## Session History route (`/session/history`)

`web/src/routes/SessionHistory.tsx` is a read-only inspector over past operator
sessions (`/operator/sessions`, `/operator/session/{id}`). The operator is
resolved server-side from the authed session.

A two-column layout: the left column lists sessions (`session_id`,
`history_len`, last timestamp); the right column shows the selected session's
detail — every history entry with its `timestamp`, `intent_type`, `text`,
`runtime_decision` (the UI styles `warn` and `block` distinctly), and `engine`.
No mutation.

## Runtime Panel and the envelope

The cockpit embeds a **Runtime Panel** (`components/cockpit/RuntimePanel.tsx`
and `components/cockpitV2/RuntimePanel.tsx`) that displays the operator's
runtime **envelope**.

- The envelope is fetched from `/runtime/envelope`. CockpitV2 loads it through
  the `cockpit` store's `runtime` slice and refreshes every 10 seconds.
- Large vectors are stripped server-side and arrive as
  `{_vector: true, dim: N}` descriptors.
- `components/runtime/EnvelopeRenderer.tsx` is a deterministic walker over the
  21 envelope layers (`events` v6 → `connective_ops` v27): `events`,
  `episodes`, `narratives`, `story_arcs`, `identity`, `trajectory`, `elins`,
  `universal_physics`, `coherence`, `external_context`,
  `physics_reasoning_context`, `reasoning_cues`, `reasoning_weights`,
  `memory_context`, `external_knowledge`, `cognitive_loop`,
  `reasoning_scaffold`, `response_shape`, `response_templates`,
  `sentence_operators`, `connective_ops`. Each layer is a collapsible section;
  vectors render as descriptor badges. The renderer performs no summarisation,
  no embedding, and no inference — it displays the envelope as the backend
  provides it.
- The envelope header surfaces `updated_at`, `envelope_decay_ts`,
  `envelope_last_replay_ts`, `last_centroid_update_ts`, the `envelope_vector`
  and `envelope_centroid` descriptors, an `envelope_drift_events` count, and
  the `elins_briefs` count.

## Data layer

- `services/runtime.ts` — `fetchRuntimeEnvelope()` (GET `/runtime/envelope`)
  and `fetchEnvelopeLatest(sessionId)` (wraps `/markov/envelope/latest`).
- `hooks/useEnvelope.ts` — fetches and caches the envelope; exposes
  `{envelope, loading, error, refresh}`.

## What the Runtime UI is not

The following appear in earlier design material but exist in no code: a
four-pane layout of a process list, log stream, diagnostics panel, and CLI;
"process cards"; a "log stream"; a standalone "drift vector widget"; and a
"system load bar". The runtime surfaces are the Session route, the Session
History route, and the cockpit Runtime Panel described above.
