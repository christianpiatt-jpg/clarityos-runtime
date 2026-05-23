/**
 * Perplexity upstream — MOCK implementation.
 *
 * Deterministic by construction:
 *   - No randomness
 *   - No time-based behavior
 *   - No external calls
 *   - tokensUsed is always 0
 *
 * Error simulation: any query containing "trigger_error" throws
 * MOCK_PERPLEXITY_ERROR for deterministic failure-path tests.
 */

import type { PerplexityRequest, PerplexityResponse } from "./types";

export async function callPerplexityMock(
  req: PerplexityRequest,
): Promise<PerplexityResponse> {
  if (req.query.includes("trigger_error")) {
    throw new Error("MOCK_PERPLEXITY_ERROR");
  }

  return {
    text: `MOCK_RESPONSE: ${req.query}`,
    tokensUsed: 0,
  };
}
