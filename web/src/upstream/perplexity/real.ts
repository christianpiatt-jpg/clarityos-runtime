/**
 * Perplexity upstream — REAL implementation.
 *
 * Constraints (per integration card):
 *   - One fixed model constant. No fallback, no endpoint switching.
 *   - One deterministic HTTP call. No retries. No backoff. No caching.
 *   - 10,000 ms timeout via AbortController.
 *   - PERPLEXITY_API_KEY read from env. Never logged.
 *   - Deterministic error mapping.
 *   - Response normalized to { text, tokensUsed } only.
 */

import type { PerplexityRequest, PerplexityResponse } from "./types";

/** Fixed Sonar model for this integration. Do not change without a new card. */
const PERPLEXITY_MODEL = "sonar-pro";

/** Fixed Sonar chat-completions endpoint. */
const PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions";

/** Fixed request timeout in milliseconds. */
const PERPLEXITY_TIMEOUT_MS = 10_000;

export class PerplexityConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PerplexityConfigError";
  }
}

export class PerplexityTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PerplexityTimeoutError";
  }
}

export class PerplexityUpstreamError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "PerplexityUpstreamError";
    this.status = status;
  }
}

export class PerplexityParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PerplexityParseError";
  }
}

export async function callPerplexityReal(
  req: PerplexityRequest,
): Promise<PerplexityResponse> {
  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) {
    throw new PerplexityConfigError(
      "PERPLEXITY_API_KEY is not set; REAL mode requires an API key.",
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    PERPLEXITY_TIMEOUT_MS,
  );

  const body: Record<string, unknown> = {
    model: PERPLEXITY_MODEL,
    messages: [{ role: "user", content: req.query }],
  };
  if (typeof req.maxTokens === "number") {
    body.max_tokens = req.maxTokens;
  }

  let response: Response;
  try {
    response = await fetch(PERPLEXITY_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if ((err as { name?: string } | null)?.name === "AbortError") {
      throw new PerplexityTimeoutError(
        `Perplexity request exceeded ${PERPLEXITY_TIMEOUT_MS}ms timeout.`,
      );
    }
    throw new PerplexityUpstreamError(
      0,
      `Perplexity network error: ${(err as Error).message}`,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw new PerplexityUpstreamError(
      response.status,
      `Perplexity upstream returned non-2xx status ${response.status}.`,
    );
  }

  let raw: unknown;
  try {
    raw = await response.json();
  } catch (err) {
    throw new PerplexityParseError(
      `Perplexity response was not valid JSON: ${(err as Error).message}`,
    );
  }

  const text = extractText(raw);
  const tokensUsed = extractTokensUsed(raw);

  return { text, tokensUsed };
}

function extractText(raw: unknown): string {
  const r = raw as {
    choices?: Array<{ message?: { content?: unknown } }>;
  } | null;
  const content = r?.choices?.[0]?.message?.content;
  if (typeof content !== "string") {
    throw new PerplexityParseError(
      "Perplexity response missing choices[0].message.content string.",
    );
  }
  return content;
}

function extractTokensUsed(raw: unknown): number {
  const r = raw as { usage?: { total_tokens?: unknown } } | null;
  const total = r?.usage?.total_tokens;
  return typeof total === "number" ? total : 0;
}
