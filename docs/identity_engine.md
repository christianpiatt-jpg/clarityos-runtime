# Identity Engine

## Purpose

`identity_engine.py` is a descriptive, read-only identity-coherence layer. It
summarises *existing* run measurements into an operator-identity profile. It
performs no personality typing, no intent inference, and no PII handling.

## Implementation location

`identity_engine.py` (repository root). Pure standard library plus four
repo-root sibling modules: `run_quality`, `cadence_math`, `stability_math`,
`trust_center_math`. It is "Phase 8B."

## Data model

The module is stateless — no store, no persistence, no vault keys, no
collection. It is a set of pure functions over a `records` list (run records,
each optionally carrying `mode`, `score`, and similar fields).

`DIMENSION_NAMES` is five: `tone`, `timing`, `decision_style`,
`escalation_style`, `trust_posture`.

## APIs / entrypoints

- `compute_identity_profile(records)` → `{score, dimensions, notes, n_runs}`.
  Five private scorers each return a `(score 0–100, descriptor)` pair — tone
  (run-quality consistency), timing (cadence variation and drift),
  decision_style (fast-vs-full mode concentration), escalation_style
  (critical-failure rate), and trust_posture (the `trust_center_math` trust
  signal). The composite `score` is the mean of the valid dimension scores.
  Empty or malformed input yields a neutral empty profile.
- `compare_surfaces(records_by_surface)` → `{per_surface, cross_surface_delta}`.
  The delta reports `n_surfaces`, `max_score`, `min_score`, `spread`, and an
  `interpretation` bucketed by spread (`aligned` ≤ 5, `mild divergence` ≤ 15,
  `noticeable divergence` ≤ 30, otherwise `significant divergence`).

## Integration points

It is a library, consumed by callers such as the operator-state layer and the
acceptance harness. It does not import `operator_state`, the Memory Vault, or
any `*_store.py` module, and it exposes no HTTP endpoint of its own.

## Invariants

- The module never raises — a failing dimension scorer is caught and reported
  as a score of `50.0` with an `error:` descriptor and a note.
- All scores are clipped to `[0, 100]`.
- It is read-only: it computes a profile from records and writes nothing.

## Non-goals

No personality typing, no intent inference, no PII handling, no persistence,
and no service endpoint. It describes; it does not classify or store.

## Fiction removed

None — this subsystem had no prior canon file; it is newly documented.
