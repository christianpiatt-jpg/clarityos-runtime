# V41 Readiness — Perplexity real wiring + kernel hardening

Status: ✅ Ready
Backend version: `3.7`
Oracle version: `perplexity_oracle.v41.1`
Kernel version: `kernel.v1.0` (logging additions)
Build: `20260507300000`

---

## What v41 ships

A live-but-guarded HTTP path against Perplexity, hidden behind
`CLARITYOS_PERPLEXITY_API_KEY` so the default behaviour stays
deterministic + offline. The kernel always sanitises ESO before it
touches ELINS, tags every fetch with an explicit
`source ∈ {mock, perplexity}`, and degrades gracefully on oracle
failure (eso=None, run still succeeds, last_error_ts surfaced).
Every `run_*` emits a structured kernel-run log line.

---

## Files added / changed

### New
- `kernel_logging.py` — `log_kernel_run`, `safe_meta`, structured-log
  contract; raw-text fields stripped from meta.
- `tests/test_v41_perplexity_kernel.py` — 41 tests.
- `V41_READINESS.md` (this file).

### Modified
- `perplexity_oracle.py`:
  - `ORACLE_VERSION` → `perplexity_oracle.v41.1`.
  - `fetch_basin_signals` branches on `_cloud_provider_active()`:
    mock fixture by default, real HTTP when API key is set.
  - New `_call_perplexity(query)` — `urllib`-based POST against the
    Perplexity chat-completions endpoint; uniform `RuntimeError` on
    HTTP / JSON failure.
  - New `_normalize_to_eso(raw, *, region_code)` — best-effort JSON
    extraction from the response body, fills the v41 ESO shape
    (`sources, facts, entities, timestamps, confidence`) and
    synthesises the legacy v35 fields (`signals, anchors,
    domain_bias`) so existing ELINS code keeps working.
  - New `sanitize_eso(eso)` — strips `body / html / raw_body /
    article_body / content / html_content / full_text / raw_html`
    keys, strips HTML tags everywhere, truncates strings to 2000
    chars; recursive over dicts + lists.
  - New `provider_status()` — returns
    `{configured, mode, endpoint, last_error_ts, last_error_message}`.
  - New `_record_error / _clear_error / get_last_error` for
    observability.
  - One-shot warning when API key is missing on first call.
- `intelligence_kernel.py`:
  - `_maybe_fetch_eso` now wraps oracle calls in try/except (any
    exception → log + record + return None), runs `sanitize_eso`
    before returning, tags `source` if absent.
  - New `_eso_source(mode, eso)` helper for the public source tag.
  - `run_c`, `run_G`, `run_ELINS`, `run_regional_ELINS`,
    `run_macro_ELINS` all wrap their work with
    `kernel_logging.log_kernel_run` (start time → finally block).
  - `run_regional_ELINS` returns `eso_source` alongside `eso_present`.
  - `kernel_status` includes `perplexity: {…}` from
    `perplexity_oracle.provider_status()`.
  - `kernel_view_for_user` adds `eso_source` (none/mock/perplexity).
- `app.py`:
  - `/me` exposes top-level `external_signal_mode` + `eso_source`
    (mirrors the kernel-view fields for clients that don't walk the
    full block).
  - Backend version `3.7`.
- `tests/conftest.py` — reset hook calls
  `perplexity_oracle._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `3.7`.
- `tests/test_v35_regional_elins.py` — version-prefix assertion
  loosened to `perplexity_oracle.v` (no longer pinned to v35).
- `BUILD_VERSION` — `20260507300000`.

---

## ESO shape (v41)

```jsonc
{
  "region_code":  "US",
  // v41 augmented fields
  "sources":      ["https://example.com/a", "https://example.com/b"],
  "facts":        ["Federal Reserve held rates steady", ...],
  "entities":     ["Federal Reserve", "Senate"],
  "timestamps":   [1715080800.0, ...],
  "confidence":   0.7,
  "source":       "mock" | "perplexity",
  // legacy v35 fields preserved (synthesised from the new ones in live mode)
  "signals":      [{"key": "pressure", "intensity": 0.62, ...}, ...],
  "anchors":      ["Federal Reserve rate path", ...],
  "domain_bias":  {"economic": 0.30, ...},
  "fetched_at":   1715080800.0,
  "version":      "perplexity_oracle.v41.1",
  "mock":         true,
  "user":         "alice"
}
```

After `sanitize_eso`:
- `body / html / raw_body / article_body / content / html_content /
  full_text / raw_html` keys are dropped.
- All strings are HTML-stripped + truncated to 2000 chars.

---

## Kernel run-log format

Every `run_*` emits one line on `clarityos.kernel.runs`:

```jsonc
{
  "kind":                  "run_regional_ELINS",
  "user_id":               "alice",
  "external_signal_mode":  "cloud_perplexity",
  "eso_source":            "mock",          // none | mock | perplexity
  "duration_ms":           42.7,
  "ok":                    true,
  "ts":                    1715080800.123,
  "version":               "kernel_logging.v41.1",
  "meta":                  { "region": "MEA", "ep_mean": 0.31, "has_eso": true }
}
```

`safe_meta` strips `text / scenario_text / input_text / raw_text /
prompt / html / body / raw_body` keys and truncates string values to
200 chars.

---

## API surface

### `/me` (additions)
```jsonc
{
  ...,
  "external_signal_mode": "cloud_perplexity",
  "eso_source":           "mock",            // none | mock | perplexity
  "intelligence_kernel": {
    "version":              "kernel.v1.0",
    "external_signal_mode": "cloud_perplexity",
    "eso_source":           "mock",
    "preferred_domains":    {...},
    "preferred_regions":    {...}
  }
}
```

### `GET /founder/intelligence/kernel/status` (additions)
```jsonc
{
  "ok": true,
  "kernel": {
    ...,
    "perplexity": {
      "configured":          false,
      "mode":                "mock",         // mock | live
      "endpoint":            "https://api.perplexity.ai/chat/completions",
      "last_error_ts":       null,
      "last_error_message":  null
    }
  }
}
```

---

## Failure modes

| Scenario | Behaviour |
| --- | --- |
| `external_signal_mode == "cloud_only"` | Oracle never called; `eso_source = "none"`. |
| Mode = `cloud_perplexity`, no API key | Mock fixture; `eso_source = "mock"`; one-shot warning logged. |
| Mode = `cloud_perplexity`, API key set, success | Live fetch; sanitised; `eso_source = "perplexity"`. |
| Mode = `cloud_perplexity`, oracle raises | Kernel logs error, records `last_error_ts`, returns `eso=None`; ELINS run completes without ESO. |
| Mode = `cloud_perplexity`, unknown region | `eso=None` (oracle raises `ValueError`, kernel returns None). |

---

## Tests

```
tests/test_v41_perplexity_kernel.py — 41 tests, all pass
Full suite — 468 passed, 0 failed
```

Coverage:
- mock-mode determinism + augmented v41 ESO shape + per-region distinct
- `sanitize_eso` strips body/html keys, drops HTML tags, truncates
  long strings, handles nested dicts, returns None on non-dict input
- `_extract_json` tolerates plain JSON, code fences, embedded prose,
  and gracefully fails on garbage
- `_normalize_to_eso` produces valid v41 shape from a simulated
  Perplexity response, returns confidence=0.0 for unparseable content
- `provider_status` reflects env config + last_error
- kernel `_maybe_fetch_eso` skips oracle in `cloud_only`, fetches in
  `cloud_perplexity`, gracefully handles failure (`eso=None` +
  `last_error_ts` recorded), tags `source` correctly, sanitises
  before returning
- `run_regional_ELINS` survives oracle failure, returns
  `eso_source` matching reality
- `kernel_logging.safe_meta` strips forbidden keys + truncates
- `log_kernel_run` returns a JSON-clean record + emits log lines for
  every `run_*` path
- `/me` exposes top-level `external_signal_mode` + `eso_source`;
  source reflects current state across cloud_only / cloud_perplexity
  + key set / unset
- `/founder/intelligence/kernel/status` includes the `perplexity`
  block with configured/mode/last_error_ts and reflects env changes

All tests run in mock mode (no real HTTP). The "live" path is
exercised by monkey-patching `perplexity_oracle.fetch_basin_signals`
or by setting `CLARITYOS_PERPLEXITY_API_KEY` to a dummy value to
verify status fields, never by hitting the network.

---

## Notes / follow-ups

- The live HTTP path is wired against
  `https://api.perplexity.ai/chat/completions` with model
  `sonar-medium-online` and a system prompt that asks for a JSON
  object. When deployed with a real API key, the response normaliser
  may need tuning if Perplexity tweaks its output format.
- `_call_perplexity` uses stdlib `urllib` to avoid adding a runtime
  dependency. If higher concurrency or richer retry policy becomes
  necessary, swap in `httpx` or a connection-pool client.
- Pre-v41 surfaces (v28–v40) are unchanged. The new ESO fields,
  `eso_source` tags, and structured log lines are additive.
