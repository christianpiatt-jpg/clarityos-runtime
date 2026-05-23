import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { callPerplexity } from "../index";
import {
  callPerplexityReal,
  PerplexityConfigError,
} from "../real";

/**
 * REAL/MOCK gating tests (run unconditionally; never hit the network).
 *
 * These verify that:
 *   - Default mode is MOCK.
 *   - PERPLEXITY_MODE=REAL routes to the REAL path (verified deterministically
 *     by missing-key behavior: REAL throws PerplexityConfigError when no key).
 *   - Mode is resolved at call time, not module import time.
 */
describe("PERPLEXITY_MODE gating (call-time)", () => {
  const originalMode = process.env.PERPLEXITY_MODE;
  const originalKey = process.env.PERPLEXITY_API_KEY;

  beforeEach(() => {
    delete process.env.PERPLEXITY_MODE;
    delete process.env.PERPLEXITY_API_KEY;
  });

  afterEach(() => {
    if (originalMode === undefined) delete process.env.PERPLEXITY_MODE;
    else process.env.PERPLEXITY_MODE = originalMode;
    if (originalKey === undefined) delete process.env.PERPLEXITY_API_KEY;
    else process.env.PERPLEXITY_API_KEY = originalKey;
  });

  it("defaults to MOCK when PERPLEXITY_MODE is unset", async () => {
    const result = await callPerplexity({ query: "ping" });
    expect(result.text).toBe("MOCK_RESPONSE: ping");
    expect(result.tokensUsed).toBe(0);
  });

  it("routes to MOCK when PERPLEXITY_MODE is any non-REAL value", async () => {
    process.env.PERPLEXITY_MODE = "STAGING";
    const result = await callPerplexity({ query: "ping" });
    expect(result.text).toBe("MOCK_RESPONSE: ping");
  });

  it("routes to REAL when PERPLEXITY_MODE=REAL (verified via missing-key error)", async () => {
    process.env.PERPLEXITY_MODE = "REAL";
    // No PERPLEXITY_API_KEY set => REAL path must throw PerplexityConfigError.
    await expect(callPerplexity({ query: "ping" })).rejects.toBeInstanceOf(
      PerplexityConfigError,
    );
  });

  it("resolves mode at call time, not import time", async () => {
    // First call: MOCK (default).
    const mockResult = await callPerplexity({ query: "a" });
    expect(mockResult.text).toBe("MOCK_RESPONSE: a");

    // Flip env mid-process; next call must route to REAL.
    process.env.PERPLEXITY_MODE = "REAL";
    await expect(callPerplexity({ query: "b" })).rejects.toBeInstanceOf(
      PerplexityConfigError,
    );

    // Flip back to MOCK; subsequent call must route to MOCK again.
    process.env.PERPLEXITY_MODE = "MOCK";
    const mockAgain = await callPerplexity({ query: "c" });
    expect(mockAgain.text).toBe("MOCK_RESPONSE: c");
  });
});

/**
 * REAL implementation tests — deterministic, no network.
 *
 * Network-dependent REAL tests are intentionally skipped unless a key is
 * present, to avoid flaky CI behavior. Shape and error mapping are validated
 * via the deterministic missing-key path.
 */
describe("callPerplexityReal (deterministic paths)", () => {
  const originalKey = process.env.PERPLEXITY_API_KEY;

  beforeEach(() => {
    delete process.env.PERPLEXITY_API_KEY;
  });

  afterEach(() => {
    if (originalKey === undefined) delete process.env.PERPLEXITY_API_KEY;
    else process.env.PERPLEXITY_API_KEY = originalKey;
  });

  it("throws PerplexityConfigError when PERPLEXITY_API_KEY is missing", async () => {
    await expect(
      callPerplexityReal({ query: "anything" }),
    ).rejects.toBeInstanceOf(PerplexityConfigError);
  });
});

const hasKey =
  typeof process.env.PERPLEXITY_API_KEY === "string" &&
  process.env.PERPLEXITY_API_KEY.length > 0;

describe.skipIf(!hasKey)("callPerplexityReal (live shape validation)", () => {
  it("returns a normalized { text, tokensUsed } shape", async () => {
    const result = await callPerplexityReal({
      query: "Return the single word: ok",
      maxTokens: 16,
    });
    expect(typeof result.text).toBe("string");
    expect(typeof result.tokensUsed).toBe("number");
    // Only the two normalized fields are part of the contract.
    expect(Object.keys(result).sort()).toEqual(["text", "tokensUsed"]);
  });
});
