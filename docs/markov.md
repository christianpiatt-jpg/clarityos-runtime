# Markov

## Purpose

Markov is the per-session temporal state subsystem. It records an ordered
history of state vectors for each conversation session, evolves a QC envelope
and a predictive envelope across turns, and runs a deterministic state-aware
chat runtime. It is cross-cutting infrastructure: a Markov state is the start
point for DEWEY trajectory forecasting and feeds the cockpit session views.
Reply generation makes no model call — Markov composes replies deterministically
from state surfaces.

## Implementation location

The Markov state store is `markov_states_store.py` (collection `markov_states`;
documented as a store in `docs/storage_stores.md`). The Markov handlers and the
4/3-1 chat runtime are in `app.py` (the `# Markov v2`, `# 4/3-1 chat runtime`,
and `# Markov v4` blocks). The transition and prediction math is in
`dewey_pipeline.py` — `predict_next_state`, `compute_noise_component`,
`compute_predictive_envelope`, `compute_envelope_metrics`,
`top_neighborhoods_with_curvature`, `similarity`, `_normalize` — which the chat
runtime orchestrates (see Non-goals for that boundary).

## Data model

- **Markov state** (`markov_states` collection, key `ms_<token>`): `{id, user,
  session_id, state_index, state_vector (768-dim, L2-normalized), qc_envelope,
  envelope_predictive_vector, envelope_metrics, timestamp}`. `state_index` is
  0-based and increases monotonically per `(user, session_id)`.
- **`qc_envelope`** — `{qc_stability, qc_drift, qc_predictive, qc_pressure}`.
  In a chat turn: `qc_stability = similarity(prev_state, new_state)`,
  `qc_drift = 1 - qc_stability`, `qc_predictive = exp(-qc_drift * 3)`, and
  `qc_pressure = mean |curvature|` over the top neighborhoods at the new state.
- **`envelope_predictive_vector`** / **`envelope_metrics`** — the Markov v3
  fields: the predicted next envelope vector and its turn-over-turn trends
  `{stability_trend, drift_trend, pressure_trend}`.
- A Markov *session* is the pair `(user, session_id)`; there is no session
  document — `list_sessions_for_user` derives session summaries from the state
  rows.

## APIs / entrypoints

- HTTP: `POST /markov/state/update` (append a client-supplied state; rejects a
  non-unit-normalized vector with 400), `GET /markov/state/latest`,
  `GET /markov/envelope/latest` (the v3 slim envelope view), `POST /markov/chat`
  (the 4/3-1 chat runtime), `GET /sessions` (the user's Markov sessions,
  metadata only), and the legacy `POST /markov` engine endpoint (a stub
  adapter — see Non-goals).
- **The 4/3-1 chat runtime** (`/markov/chat`) — a deterministic processor
  pipeline: **Observer** (embed the message) → **Interpreter** (fold in the
  previous state) → **Regulator** (QC-weighted blend) → **Projector** (blend
  with the DEWEY-predicted next state) → **-1 Subtractive** (subtract a noise
  component). It then updates the QC envelope, evolves the v3 predictive
  envelope, builds the v3.5 transmitter recall bundle, runs the v4 generator,
  and persists the new state.
- **Markov v4 — state-aware generator** (`_generate_state_aware_reply`) —
  deterministic, no model call; maps the QC envelope and transmitter context to
  surface labels (state / trend / anchor / domain) and composes a
  one-to-two-sentence reply.
- **`markov_states_store`** — `create`, `new_id`, `latest_for`,
  `next_index_for`, `recent_for`, `list_sessions_for_user`.
  `_persist_markov_state` in `app.py` is the shared append path for
  `/markov/state/update` and `/markov/chat`.

## Integration points

- **Storage** — Markov state is persisted only through `markov_states_store`
  (`docs/storage_stores.md`).
- **DEWEY** — the runtime's Projector and -1 Subtractive stages call
  `dewey_pipeline` over the user's DEWEY neighborhoods, and DEWEY's
  `/trajectory/forecast` reads the latest Markov state as its start vector
  (`docs/dewey.md`). Message embedding also goes through DEWEY's pipeline.
- **ELINS / Envelope base layer** — a chat turn runs the Envelope v3
  decay/refresh step, and the v3.5 transmitter surfaces ELINS brief matches and
  anchors.
- **Engine catalog** — the legacy `POST /markov` engine is registered in the
  cockpit engine catalog.

## Invariants

- `state_index` is 0-based and strictly increasing per `(user, session_id)` —
  `next_index_for` returns `latest.state_index + 1`.
- `POST /markov/state/update` rejects a state vector whose norm is not within
  0.01 of 1.0.
- Given the message embedding, the 4/3-1 chat runtime is fully deterministic —
  every processor stage is vector math and the v4 reply generator makes no
  model call.
- The runtime degrades gracefully on the first turn: with no prior state it
  seeds `prev_state` from the observed message and uses an identity QC
  envelope.
- `_persist_markov_state` always fills the v3 fields — `envelope_predictive_vector`
  defaults to the state vector and `envelope_metrics` to an all-zero trend
  dict — so reads of legacy (pre-v3) states remain well-formed.
- Markov state advances only on an explicit request; there is no background
  loop.

## Non-goals

- Markov is **not** a scheduler — no background thread and no cadence; state
  advances only when `/markov/state/update` or `/markov/chat` is called.
- Markov is not DEWEY — it consumes `dewey_pipeline` geometry and DEWEY
  neighborhoods, but the neighborhood, basin, and trajectory logic is DEWEY's
  (`docs/dewey.md`). The predictive helpers in `dewey_pipeline.py` appear here
  only in their Markov role.
- Markov is not Storage — the `markov_states` store is documented in
  `docs/storage_stores.md`; this doc covers the behavior layered over it.
- The v4 chat runtime is not an LLM chat runtime — `_generate_state_aware_reply`
  composes the reply deterministically from state surfaces, with no generative
  model call.
- No billing, membership, ESO, or search semantics.

## Fiction removed

None. Every construct the 10f instruction flagged as possibly fictional is
implemented and documented above: the **Markov chat runtime** is
`POST /markov/chat`; the **4/3-1 architecture** is that runtime's labelled
processor pipeline; the **predictive envelope** is Markov v3
(`compute_predictive_envelope`, `envelope_predictive_vector`,
`/markov/envelope/latest`); and **Observer / Interpreter / Regulator /
Projector** are the four named processor stages of the 4/3-1 runtime, followed
by the -1 Subtractive constraint. Two precise notes rather than removed
fiction: the legacy `POST /markov` engine endpoint is a stub adapter
(`markov_adapter`, which returns a `"(markov-stub) …"` string), and "chat" in
the v4 runtime does not mean LLM generation — the reply is composed
deterministically.
