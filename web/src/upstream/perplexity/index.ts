/**
 * Perplexity upstream — public entry point.
 *
 * REAL/MOCK gating is resolved AT CALL TIME from PERPLEXITY_MODE.
 * This preserves deterministic test isolation: tests and runtime configuration
 * can change the mode per invocation without re-importing the module.
 *
 * Default mode: MOCK.
 *   - Tests: MOCK
 *   - Cloud Run staging: MOCK
 *   - Cloud Run production: REAL only by explicit env configuration
 */

import { callPerplexityReal } from "./real";
import { callPerplexityMock } from "./mock";
import type { PerplexityRequest, PerplexityResponse } from "./types";

export type { PerplexityRequest, PerplexityResponse } from "./types";

export async function callPerplexity(
  req: PerplexityRequest,
): Promise<PerplexityResponse> {
  const mode = process.env.PERPLEXITY_MODE ?? "MOCK";
  return mode === "REAL"
    ? callPerplexityReal(req)
    : callPerplexityMock(req);
}
