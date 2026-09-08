/** #161 -- the sha fence and the stop mark. */
import { describe, it, expect } from "vitest";
import { normSha, shortSha, stopMark } from "../wire";

describe("normSha / shortSha", () => {
  it("\u2605 \"unknown\" is not a sha; case and whitespace fold", () => {
    expect(normSha("unknown")).toBeNull();
    expect(normSha(" ABC1234DEF ")).toBe("abc1234def");
    expect(normSha(null)).toBeNull();
    expect(shortSha("bb23e509ae3cad3156103d3d4fa47caa9974ada5")).toBe("bb23e50");
    expect(shortSha(undefined)).toBe("unknown");
  });
});
describe("stopMark", () => {
  it("end_turn and absent -> no mark; anything else -> its word", () => {
    expect(stopMark("end_turn")).toBeNull();
    expect(stopMark(null)).toBeNull();
    expect(stopMark(undefined)).toBeNull();
    expect(stopMark("max_tokens")).toBe("max_tokens");
    expect(stopMark("refusal")).toBe("refusal");
  });
});
