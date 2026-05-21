# Perplexity ESO

## Purpose

The Perplexity ESO is the external-signal provider for the regional ELINS
pipeline. It returns an **ESO — External Signal Object** — a structured bundle
of signals, anchors, and domain bias for one regional basin. It is a
single-provider signal feed, not a search engine: by default it returns a
deterministic per-region fixture so the runtime works offline; a live
Perplexity API call is opt-in behind an env key.

## Implementation location

Repo-root module `perplexity_oracle.py` (version `perplexity_oracle.v41.1`;
introduced v35, live HTTP client added v41).

## Data model

- **Regions** — `SUPPORTED_REGIONS = (US, EU, MEA, APAC, Markets, Tech)`.
- **`REGION_FIXTURES`** — a static per-region template: a list of `signals`
  (each `{key, intensity, weight, source, anchor}`), an `anchors` list, and a
  `domain_bias` map. Every value is constant, so the same call returns the
  same object.
- **ESO shape** — the contract `regional_elins` consumes: `{region_code,
  signals[], anchors[], domain_bias{}, fetched_at, version, mock, source,
  user}`, plus the v41 augmented fields `{sources[], facts[], entities[],
  timestamps[], confidence}`.
- **Observability state** — module-level `_last_error_ts` / `_last_error_msg`
  (cleared on a successful live call) and a one-shot `_warned_missing_key`
  flag. This is the only state the module keeps; nothing is persisted.

## APIs / entrypoints

- `fetch_basin_signals(region_code, *, user=None, mode="auto")` → an ESO dict
  or `None`. `mode="auto"` calls live Perplexity when
  `CLARITYOS_PERPLEXITY_API_KEY` is set, otherwise returns the fixture;
  `mode="mock"` always returns the fixture; `mode="off"` returns `None`. An
  unknown `region_code` raises `ValueError`.
- `is_eso_enabled(user_doc)` → `True` iff the user's `external_signal_mode` is
  `cloud_perplexity`.
- `sanitize_eso(eso)` → a defensive copy with HTML stripped, strings truncated
  to 2000 chars, and body/HTML-style keys dropped.
- `provider_status()` → `{configured, mode, endpoint, last_error_ts,
  last_error_message}`.
- `get_last_error()` → `{ts, message}`.
- `REGION_FIXTURES` — exported for offline UI and tests.

## Integration points

- **regional_elins** — the primary consumer; the ESO shape is the contract it
  reads.
- **intelligence_kernel** — `_maybe_fetch_eso` wraps the oracle, sanitises the
  result, and tags its source; an oracle failure degrades gracefully (the run
  completes with `eso=None`).
- **elins_scheduler** — the macro scheduler's `external_signal_mode`
  (`cloud_only` / `cloud_perplexity`) decides whether a macro pass fetches an
  ESO at all.
- **Perplexity API** — the single external dependency, reached over stdlib
  `urllib`, gated by `CLARITYOS_PERPLEXITY_API_KEY` (endpoint overridable via
  `CLARITYOS_PERPLEXITY_ENDPOINT`).

## Invariants

- **Deterministic mock** — fixture mode is pure: the same `region_code` yields
  the same ESO, including a deterministic `fetched_at`.
- **Live is opt-in** — with no API key set, every call falls back to the
  fixture and logs a single one-shot warning.
- **Stable shape** — the mock and live paths return the same ESO shape, so
  downstream code is indifferent to the source.
- **Sanitised egress** — every live ESO passes through `sanitize_eso` before
  it leaves the module: HTML stripped, long strings truncated, and
  `body` / `html` / `raw_body` / `content`-style keys dropped.
- **Failures are typed** — a live-path failure (timeout, non-2xx, JSON error)
  raises `RuntimeError`; the kernel wraps it so one failed fetch never breaks
  an ELINS run.
- `mode="off"` always returns `None`; an unknown region always raises
  `ValueError`.

## Non-goals

- ESO is not a search engine and not a search orchestrator — it does not
  crawl, rank, or aggregate results.
- It is single-provider (Perplexity only): there is no provider registry and
  no provider-selection logic.
- It produces no intelligence itself — it shapes an external signal into the
  ESO contract; interpreting that signal is the ELINS pipeline's job.
- It hosts no UI and persists nothing; its only state is transient error
  observability.

## Fiction removed

Earlier layout drafts framed ESO as an "External Search Orchestration" layer
with a provider registry, provider-selection logic, query aggregation, result
ranking, semantic ranking, and multi-provider ensembles. None of that exists.
"ESO" is the **External Signal Object** — a data contract — and
`perplexity_oracle.py` is a single-provider fetcher that returns either a
static per-region fixture or one normalised Perplexity response. There is no
second provider, no ranking, and no aggregation; the only post-processing is
`_normalize_to_eso` (shape coercion) and `sanitize_eso` (payload hygiene).
Those drafts also listed the model router and the cockpit as ESO integration
points — they are not; the ESO flows to `regional_elins` and the intelligence
kernel.
