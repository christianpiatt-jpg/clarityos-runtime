import { describe, it, expect } from "vitest";
import { callPerplexityMock } from "../mock";

describe("callPerplexityMock", () => {
  it("returns deterministic output for a simple query", async () => {
    const result = await callPerplexityMock({ query: "hello" });
    expect(result.text).toBe("MOCK_RESPONSE: hello");
    expect(result.tokensUsed).toBe(0);
  });

  it("returns deterministic output for a multi-sentence query", async () => {
    const query = "First sentence. Second sentence. Third sentence.";
    const result = await callPerplexityMock({ query });
    expect(result.text).toBe(`MOCK_RESPONSE: ${query}`);
    expect(result.tokensUsed).toBe(0);
  });

  it("throws MOCK_PERPLEXITY_ERROR when query contains trigger_error", async () => {
    await expect(
      callPerplexityMock({ query: "please trigger_error now" }),
    ).rejects.toThrow("MOCK_PERPLEXITY_ERROR");
  });

  it("is deterministic across repeated calls", async () => {
    const a = await callPerplexityMock({ query: "same" });
    const b = await callPerplexityMock({ query: "same" });
    expect(a).toEqual(b);
  });
});
