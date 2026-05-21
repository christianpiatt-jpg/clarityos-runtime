# Acceptance run run-20260512T093041Z-9b2f

> **REALISTIC EXAMPLE.** Curated to illustrate timing variance and
> per-iteration growth. Not produced by execution. Companion to the
> cleaner all-pass example at
> `tests/acceptance/expected_outputs/sample_report.md`.

- mode: **full**
- started: 2026-05-12T09:30:41.012Z
- finished: 2026-05-12T10:04:18.493Z
- result: **PASS**

## 01_onboarding_per_surface — PASS (312667ms)

- web onboarding for op_a: 33124ms ok
- phone onboarding for op_a: 51308ms ok
- desktop onboarding for op_a: 31221ms ok
- web onboarding for op_b: 32987ms ok
- phone onboarding for op_b: 49810ms ok
- desktop onboarding for op_b: 30714ms ok

> Note: phone onboarding (~50s) consistently runs slower than web/desktop
> (~31s) — Maestro spawn + Expo launch overhead. Within the 10-minute
> budget but worth tracking if it climbs.

## 02_cross_surface_jump — PASS (411082ms)

- web: 1 ELINS, 1 threads
- cross-surface jump: 408950ms ok

> Note: surface jump completed in 6.8 minutes, well under the 10-minute
> threshold but slower than the synthetic sample due to a real Expo
> simulator boot + desktop binary launch.

## 03_two_operators_concurrent — PASS (71542ms)

`{"op_a":{"handle":"op_a","ms":35711,"error":null,"counts":{"threads":1,"elins":1,"projects":0}},"op_b":{"handle":"op_b","ms":34928,"error":null,"counts":{"threads":1,"elins":1,"projects":0}}}`

- onboarding for op_a: 35711ms ok
- onboarding for op_b: 34928ms ok
- vault isolation: confirmed disjoint sets (op_a: 1t/1e/0p, op_b: 1t/1e/0p)

## 04_artifact_presence — PASS (102991ms)

`{"operator":"op_a","surfaces":[{"surface":"web","counts":{"threads":1,"elins":1,"projects":0}},{"surface":"desktop","counts":{"threads":1,"elins":1,"projects":0}},{"surface":"phone","counts":{"threads":1,"elins":1,"projects":0}}]}`

- presence ok: web=1e/1t · desktop=1e/1t · phone=1e/1t

## 05_stability_window — PASS (318011ms)

`{"iterations":[{"index":1,"pass":true,"duration_ms":102220,"web_elins_count":1},{"index":2,"pass":true,"duration_ms":105441,"web_elins_count":2},{"index":3,"pass":true,"duration_ms":110218,"web_elins_count":3}],"stats":{"iterations":3,"pass_count":3,"mean_ms":105959.67,"max_ms":110218,"min_ms":102220,"stddev_ms":3286.41},"monotonicity_pass":true}`

- iteration 1: 102220ms ok
- iteration 2: 105441ms ok
- iteration 3: 110218ms ok
- timing variance ok: max=110218ms mean=105960ms ratio=1.04

> Note: each iteration grew slightly (102s → 105s → 110s). The 1.04
> max/mean ratio is well under the 2.0 bound, but the monotonic
> upward trend is worth a glance — if a future run pushes the ratio
> above ~1.5, a P2 incident is warranted to investigate progressive
> slowdown.
