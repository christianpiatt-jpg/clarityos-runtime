/**
 * Perplexity upstream module — public types.
 *
 * Additive-only contract for the TypeScript runtime (v0.2 web surface).
 * No state, no caching, no persistence. No cross-runtime coupling.
 */

export interface PerplexityRequest {
  query: string;
  maxTokens?: number;
}

export interface PerplexityResponse {
  text: string;
  tokensUsed: number;
}
