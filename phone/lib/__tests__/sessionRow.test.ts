/** #161 -- the history row names the model that answered (web #147). */
import { describe, it, expect } from "vitest";
import { modelLabel } from "../sessionRow";

describe("modelLabel", () => {
  it("\u2605 model=… when the provider matches the engine; · mock when mock", () => {
    expect(modelLabel({ engine: "claude", model_id: "anthropic:claude-haiku-4-5-20251001", mock: false }))
      .toBe("model=anthropic:claude-haiku-4-5-20251001");
    expect(modelLabel({ engine: "local", model_id: "local:llama3.1", mock: true }))
      .toBe("model=local:llama3.1 \u00b7 mock");
  });
  it("a routed answerer names both; a pre-#147 row reads engine=… as before", () => {
    expect(modelLabel({ engine: "copilot", model_id: "google:gemini-2.5-flash" }))
      .toBe("engine copilot \u2192 routed google:gemini-2.5-flash");
    expect(modelLabel({ engine: "claude" })).toBe("engine=claude");
    expect(modelLabel({ engine: "claude", model_id: null })).toBe("engine=claude");
  });
});
