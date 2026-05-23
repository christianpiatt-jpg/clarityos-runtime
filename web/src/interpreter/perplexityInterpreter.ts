/**
 * Perplexity interpreter module.
 *
 * Additive integration seam. This module:
 *   - Accepts interpreter input.
 *   - Calls callPerplexity() from the upstream module.
 *   - Returns a structured interpreter response.
 *
 * It does NOT:
 *   - mutate state
 *   - modify routing or rendering
 *   - alter operator-loop semantics
 *   - modify the vault
 *
 * Registry note: at the time this seam was created, no TypeScript interpreter
 * registry existed under web/src/. This module is therefore exported but not
 * auto-registered. See web/src/upstream/perplexity/UPSTREAM.md for the
 * documented integration seam.
 */

import { callPerplexity } from "../upstream/perplexity";

export interface PerplexityInterpreterResult {
  type: "perplexity";
  output: string;
}

export async function interpretWithPerplexity(
  input: string,
): Promise<PerplexityInterpreterResult> {
  const result = await callPerplexity({ query: input });
  return {
    type: "perplexity",
    output: result.text,
  };
}
