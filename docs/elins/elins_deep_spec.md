# ELINS

## Overview

ELINS is the ClarityOS analysis subsystem. The name covers **two distinct
codebases** that share the `elins` prefix but are otherwise separate:

- **ELINS-canonical** — the scenario-text analysis pipeline: `ELINS/standard_elins.py`,
  `forecast_engine.py`, `regional_elins.py`, `ELINS/elins_project.py`,
  `elins_scheduler.py`, `elins_dashboard.py`, and the `intelligence_kernel.py`
  entry points.
- **ELINS-regression** — a separate analytics suite over stored *regression*
  runs: the `elins_run_*.py` modules and `elins_persistence*.py`.

The two have separate pipelines, separate persistence, and separate data
models. This document specifies both.

Note: The `el_ins/` package (`el_ins_analyzer`, `el_ins_store`,
`el_ins_export`) is a distinct per-turn analyzer gated by
`operator_state.el_ins_per_turn` (see `docs/operator_state.md`). Despite
the namespace similarity, it is not part of the ELINS-canonical long-arc
pipeline documented here.

## ELINS-canonical — the pipeline

`ELINS/standard_elins.generate_ELINS(text, ...)` runs a deterministic, lexical
pipeline — no embeddings, no model calls, no randomness. `LAYER_NAMES` has
eleven entries (the v34 `forecast_engine` layer was inserted into the original
ten):

0. `input_phase` — normalise the text; derive a `scenario_id` (`sc_<16 hex>`, a
   SHA-256 of the text); count characters and words.
1. `primitives` — lexical extraction of the six EP primitives → `raw_scores`
   and `intensities` (each `raw / 4.0`, clipped to `[0, 1]`).
2. `domain_mapping` — keyword scoring across eight `DOMAIN_HINTS`; yields the
   `effective_top` domain.
3. `ep_field_summary` — `stress_total`, `relief_total`, `net`, `dominant`,
   `intensity_mean`.
4. `causal_chain` — pairwise primitive co-occurrence edges; threshold `0.05`,
   edge weight `min(intensity_a, intensity_b)`.
5. `stress_relief` — a `relief_dominant` / `stress_dominant` / `balanced`
   signal (±`0.15` band); `net_pressure = -net`.
6. `forecast_5day` — a deterministic 5-day net trajectory, 12%-per-step mean
   reversion.
7. `forecast_engine` — the v34 envelope block (see "Forecast engine").
8. `synthesis` — `top_primitive`, `domain`, `signal`, `trend`, scores.
9. `qc_s_elins` — the inline S-ELINS self-check (see "S-ELINS QC").
10. `output_object` — a flat mirror of the result: `scenario_id`, `summary`,
   `ts`, `version` (`elins.v34.1`).

### EP primitives

`PRIMITIVE_KEYS` is six: **pressure, tension, trust, drift, contradiction,
alignment**. Each is extracted by lexical match against `_PRIMITIVE_LEXICON`
(lowercase substring tokens with per-match weights); occurrences are capped at
five per token, summed, and normalised `value / 4.0` clipped to `[0, 1]`.

- `STRESS_PRIMITIVES` — pressure, tension, drift, contradiction.
- `RELIEF_PRIMITIVES` — trust, alignment.

The `drift` primitive here is one of the six lexical scores. It is unrelated to
the ELINS-regression `drift` classifier described below.

### Forecast engine

`forecast_engine.py` projects each primitive forward with the decay law:

`ep(D + n) = ep0 · exp(-λ · n)`

`DEFAULT_LAMBDAS`: pressure `0.20`, tension `0.18`, trust `0.10`, drift `0.05`,
contradiction `0.25`, alignment `0.10` (drift decays slowest, by design).
Public functions: `compute_envelope`, `compute_multi_envelope`
(magnitude-weighted, normalised), `compute_domain_envelope` (over seven
`DOMAIN_VECTORS`), `compute_chain_envelope` (summed with
`DEFAULT_CHAIN_ATTENUATION = (1.0, 0.8, 0.65, 0.55, 0.5, 0.45)`).
`compute_forecast_block` emits `primitive_envelopes`, `multi_envelope`,
`domain_envelopes`, `chain`, and `chain_envelope` (`version` `forecast.v34.1`).
Horizons are clamped to `[1, 30]` days and rounded to six decimals.

### S-ELINS QC

`generate_S_ELINS` re-extracts the primitives and compares them to the run's.
The check passes when `max_delta < S_ELINS_PASS_THRESHOLD` (`0.05`); it reports
`alignment_score = max(0, 1 - max_delta · 4)`.

### Regional and macro ELINS

`regional_elins.run_regional_elins` wraps `generate_ELINS` for six regions —
`US`, `EU`, `MEA`, `APAC`, `Markets`, `Tech` — each with a `REGION_PROFILES`
entry (scaffold sentence, entity bumps, domain overlay, λ overlay) and optional
ESO signal blending. `elins_scheduler.py` runs the macro pass (one global plus
six regional analyses per tick), cadence-gated by `elins_scheduler_config`
(`off` / `daily` / `3x_week` / `weekly`; `cloud_only` / `cloud_perplexity`).

### Persistence

ELINS-canonical does **not** use the Memory Vault (see
`docs/memory_vault.md`). `ELINS/elins_project.py` is its own store
(in-memory plus Firestore) with separate collections for runs,
primitives, domains, baseline, config, regional runs, macro runs, and the
entity graph. `save_daily_run` writes a record keyed `{user}_{YYYY-MM-DD}` —
`id`, `user`, `day`, `saved_ts`, `scenario_id`, `summary`, `primitives`,
`domain_top`, `domain_scores`, `ep_field_summary`, `elins` (the full payload),
`input_word_count`, `version`. The write is idempotent on a same-day collision.

### Kernel integration

`intelligence_kernel.run_ELINS(user, text, ...)` (see
`docs/intelligence_kernel.md`) calls `generate_ELINS`, attaches the
S-ELINS QC result as `elins["qc"]`, persists via `save_daily_run` and the
index helpers, records an ELINS interaction in Operator State (see
`docs/operator_state.md`; analysis-derived metadata only — no raw text),
and emits a kernel-run log line. It returns `{ok, elins, run_id, qc, baseline, model_id}`.
`run_regional_ELINS` and `run_macro_ELINS` are the regional and macro entry
points.

## ELINS-regression — the analytics suite

The `elins_run_*.py` modules are a separate, Unit-numbered analytics suite over
stored **regression runs** (single-party / economic-coercion scoring). Ten
modules: `composite`, `dashboard`, `diff`, `drift`, `drift_magnitude`,
`drift_series`, `drift_severity`, `ordering`, `summary`, `summary_multi`.

### Regression drift

`elins_run_drift.detect_drift(runs)` classifies the score trajectory of each
`pair_id` (a `single_party::economic_coercion` composite present in every run)
into `stable`, `trending_up`, `trending_down`, or `volatile`. Companion
modules: `drift_magnitude` (adds `range`, `max_swing`, `mean_step`),
`drift_severity` (fuses direction and magnitude into labels such as
`trending_up_strong`, via `max_swing` thresholds `0 / ≤2 / ≤4 / ≥5` →
`none / weak / moderate / strong`), and `drift_series` (raw score and band
series). Regression drift requires at least two runs; `pair_id`s with gaps are
dropped. This is multi-run trajectory analysis — it is not the EP `drift`
primitive.

### Regression persistence

`elins_persistence_sqlite.py` stores runs in a single SQLite `runs` table:
`run_id`, `envelope_json`, `notes`, `tags`, `archived`. The envelope is
`{metadata: {created_at, source, evidence_dir, engine_version}, result: <payload>}`,
where `source` is `single` / `batch` / `directory` and `engine_version` is
`elins-19`. `run_id` must match `^[A-Za-z0-9_-]+$`.

## What ELINS is not

The following appear in earlier design material but exist in no code: a
five-stage `Input → Processing → Curvature → Drift → Output` architecture; a
`sphere / pentagon / rings` geometric report; a "metadata cloud"; and a
`Detect → Classify → Generate → Validate → Propagate` loop. There is no ELINS
`curvature` classifier — `curvature` is a DEWEY concept
(`dewey_pipeline.compute_curvature`) — and there is no `center` classifier of
any kind, in ELINS or elsewhere.

## Constants

Version strings: `elins.v34.1` (pipeline output), `selins.v33.1` (S-ELINS),
`forecast.v34.1` (forecast block), `elins.v33.1` / `elins.regional.v35.1` /
`entity_graph.v37.1` (project records), `elins-19` (regression engine). The
canonical pipeline is deterministic and lexical — no model calls, no network,
no randomness.
