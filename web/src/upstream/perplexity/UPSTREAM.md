# Perplexity Upstream Module

Additive Perplexity research-engine adapter for the authoritative TypeScript
runtime under `web/src/`. Python paths are out of scope and untouched.

This module does not modify routing, rendering, operator-loop semantics, or
the vault. It introduces no state, caching, or persistence.

## Public API

```ts
import { callPerplexity } from "./index";
import type {
  PerplexityRequest,
  PerplexityResponse,
} from "./types";

const result: PerplexityResponse = await callPerplexity({
  query: "What is...?",
});
```

`PerplexityResponse` is normalized to exactly `{ text, tokensUsed }`. No
additional fields are part of the contract.

## REAL/MOCK gating (call-time)

Mode is resolved on every invocation from `process.env.PERPLEXITY_MODE`:

- Unset or any value other than `REAL` => MOCK.
- `REAL` => REAL Sonar call.

Call-time resolution is mandatory. Tests and runtime configuration may flip
`PERPLEXITY_MODE` between calls without re-importing the module.

## Environment variables

| Name                  | Required        | Purpose                                  |
| --------------------- | --------------- | ---------------------------------------- |
| `PERPLEXITY_MODE`     | No (default MOCK) | Gates REAL vs MOCK at call time.        |
| `PERPLEXITY_API_KEY`  | REAL only       | Bearer token for Sonar chat completions. |

The API key is never logged.

## Deployment posture

- Tests: MOCK.
- Cloud Run staging: MOCK.
- Cloud Run production: REAL only by explicit env configuration.

## REAL implementation constraints

- Fixed model constant: `sonar-pro` (declared in `real.ts`).
- Fixed endpoint: `https://api.perplexity.ai/chat/completions`.
- Single deterministic HTTP call via built-in `fetch`.
- 10,000 ms timeout via `AbortController`.
- No retries, no backoff, no caching, no fallback model.
- Deterministic error mapping:
  - Missing API key => `PerplexityConfigError`.
  - Timeout (`AbortError`) => `PerplexityTimeoutError`.
  - Non-2xx => `PerplexityUpstreamError`.
  - Malformed body or missing fields => `PerplexityParseError`.

## MOCK implementation constraints

- No randomness, no time-based behavior, no external calls.
- `tokensUsed` is always `0`.
- Any query containing `trigger_error` throws `MOCK_PERPLEXITY_ERROR`.

## Interpreter integration seam

A `perplexityInterpreter` module exists at
`web/src/interpreter/perplexityInterpreter.ts` and exports:

```ts
export async function interpretWithPerplexity(
  input: string,
): Promise<{ type: "perplexity"; output: string }>;
```

### Registry status

At the time this module was added, **no TypeScript interpreter registry
existed under `web/src/`**. Per the integration card, this card does not
invent a registry or operator-loop architecture.

**Pending registry hookup:** when an interpreter registry is introduced under
`web/src/`, register the Perplexity interpreter as:

```ts
import { interpretWithPerplexity } from "../interpreter/perplexityInterpreter";

registry["perplexity"] = interpretWithPerplexity;
```

This seam is intentionally inert until a registry exists. No routing,
rendering, or operator-loop behavior changes as a result of this module.

## Out of scope

- Python path changes.
- Router behavior.
- Render pipeline.
- Operator-loop redesign.
- Caching, persistence, or state.
- Cross-runtime wiring.
