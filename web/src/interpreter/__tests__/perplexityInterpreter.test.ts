import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { interpretWithPerplexity } from "../perplexityInterpreter";

describe("interpretWithPerplexity", () => {
  const originalMode = process.env.PERPLEXITY_MODE;

  beforeEach(() => {
    delete process.env.PERPLEXITY_MODE; // default => MOCK
  });

  afterEach(() => {
    if (originalMode === undefined) delete process.env.PERPLEXITY_MODE;
    else process.env.PERPLEXITY_MODE = originalMode;
  });

  it("returns a structured { type, output } result in MOCK mode", async () => {
    const result = await interpretWithPerplexity("hello world");
    expect(result).toEqual({
      type: "perplexity",
      output: "MOCK_RESPONSE: hello world",
    });
  });

  it("propagates MOCK_PERPLEXITY_ERROR for trigger_error inputs", async () => {
    await expect(
      interpretWithPerplexity("please trigger_error"),
    ).rejects.toThrow("MOCK_PERPLEXITY_ERROR");
  });

  it("does not include any fields beyond the documented contract", async () => {
    const result = await interpretWithPerplexity("shape check");
    expect(Object.keys(result).sort()).toEqual(["output", "type"]);
  });
});
