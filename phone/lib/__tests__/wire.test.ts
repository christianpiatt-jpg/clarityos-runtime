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
  it("#196 -- only a \"cut\" marks; the phone wire still sends neither field", () => {
    // #196 -- ONLY the backend vocabulary's "cut" marks. The raw token
    // is what the mark NAMES; the class is what decides.
    expect(stopMark("max_tokens", "cut")).toBe("max_tokens");
    expect(stopMark("length", "cut")).toBe("length");
    expect(stopMark("SAFETY", "cut")).toBe("SAFETY");
    // the #196 bug: a NORMAL finish from OpenAI / Gemini / Ollama
    expect(stopMark("stop", "normal")).toBeNull();
    expect(stopMark("STOP", "normal")).toBeNull();
    expect(stopMark("end_turn", "normal")).toBeNull();
    // the other direction: a word the table does not know is NOT a cut
    expect(stopMark("tool_use", "unknown")).toBeNull();
    // no class at all (a mock, an older wire) marks nothing
    expect(stopMark("max_tokens", undefined)).toBeNull();
    expect(stopMark("max_tokens", null)).toBeNull();
    expect(stopMark(null, "cut")).toBeNull();
    expect(stopMark("", "cut")).toBeNull();
  });
  it("#196 -- \"refusal\" was this file's example of a mark; under CT-1's\n      table it is UNKNOWN and now renders NOTHING", () => {
    // Anthropic really does return it and it really is a cut. The table is
    // CT-1's and his rule for an unlisted word is unknown, so the mark is
    // gone until he rules -- pinned here so the loss is deliberate, not a
    // deleted assertion. stop_vocabulary.py names the whole set.
    expect(stopMark("refusal", "unknown")).toBeNull();
  });
});
