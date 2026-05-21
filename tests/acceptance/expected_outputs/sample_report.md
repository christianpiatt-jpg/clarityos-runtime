# Acceptance run run-20260508T142133Z-7a3c

> **EXAMPLE ONLY.** This file lives at `tests/acceptance/expected_outputs/`
> and demonstrates the shape of `report.md` written by `runner.ts`. It is
> not produced by any real run.

- mode: **full**
- started: 2026-05-08T14:21:33.214Z
- finished: 2026-05-08T14:48:51.776Z
- result: **PASS**

## 01_onboarding_per_surface — PASS (287143ms)

- web onboarding for op_a: 31420ms ok
- phone onboarding for op_a: 47215ms ok
- desktop onboarding for op_a: 28940ms ok
- web onboarding for op_b: 30811ms ok
- phone onboarding for op_b: 45203ms ok
- desktop onboarding for op_b: 27554ms ok

## 02_cross_surface_jump — PASS (184226ms)

- web: 1 ELINS, 1 threads
- cross-surface jump: 184110ms ok

## 03_two_operators_concurrent — PASS (62841ms)

`{"op_a":{"handle":"op_a","ms":31104,"error":null,"counts":{"threads":1,"elins":1,"projects":0}},"op_b":{"handle":"op_b","ms":30992,"error":null,"counts":{"threads":1,"elins":1,"projects":0}}}`

- onboarding for op_a: 31104ms ok
- onboarding for op_b: 30992ms ok
- vault isolation: confirmed disjoint sets (op_a: 1t/1e/0p, op_b: 1t/1e/0p)

## 04_artifact_presence — PASS (91320ms)

`{"operator":"op_a","surfaces":[{"surface":"web","counts":{"threads":1,"elins":1,"projects":0}},{"surface":"desktop","counts":{"threads":1,"elins":1,"projects":0}},{"surface":"phone","counts":{"threads":1,"elins":1,"projects":0}}]}`

- presence ok: web=1e/1t · desktop=1e/1t · phone=1e/1t

## 05_stability_window — PASS (274332ms)

`{"iterations":[{"index":1,"pass":true,"duration_ms":91110,"web_elins_count":1},{"index":2,"pass":true,"duration_ms":91560,"web_elins_count":2},{"index":3,"pass":true,"duration_ms":91490,"web_elins_count":3}],"stats":{"iterations":3,"pass_count":3,"mean_ms":91386.67,"max_ms":91560,"min_ms":91110,"stddev_ms":192.34},"monotonicity_pass":true}`

- iteration 1: 91110ms ok
- iteration 2: 91560ms ok
- iteration 3: 91490ms ok
- timing variance ok: max=91560ms mean=91387ms ratio=1.00
