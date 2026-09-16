/** #161 -- the sha fence and the stop mark. */
import { describe, it, expect } from "vitest";
import { normSha, shortSha, stopMark, readCurrency, summaryCurrency, turnCaption, UNSTAMPED_CAPTION, healthWord } from "../wire";

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

describe("#161a -- the fence as the web renders it (readCurrency / turnCaption)", () => {
  it("\u2605 fresh needs BOTH axes; one broken is aged; no stamp is old whatever the sha", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: "abc", live_sha: "ABC" })).toBe("fresh");
    expect(readCurrency({ made_turn: 3, now_turn: 4, made_sha: "abc", live_sha: "abc" })).toBe("aged");
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: "abc", live_sha: "def" })).toBe("aged");
    expect(readCurrency({ made_turn: 3, now_turn: 4, made_sha: "abc", live_sha: "def" })).toBe("old");
    expect(readCurrency({ made_turn: null, now_turn: 3, made_sha: "abc", live_sha: "abc" })).toBe("old");
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: "unknown", live_sha: "unknown" })).toBe("aged");
  });
  it("no summary is none, a different kind from old; the caption names an absent stamp", () => {
    expect(summaryCurrency({ summary: null }, "abc")).toBe("none");
    expect(summaryCurrency({ summary: "s", summary_turn: 2, message_count: 2, summary_commit_sha: "abc" }, "abc")).toBe("fresh");
    expect(turnCaption({ made_turn: 2, now_turn: 5 })).toBe("made turn 2 · now turn 5");
    expect(turnCaption({ made_turn: null, now_turn: 5 })).toBe(UNSTAMPED_CAPTION);
  });
});

describe("#151 -- the cloud probe's word", () => {
  it("\u2605 401 / 403 are the two auth words; another status names itself; none is unreachable; never a server string", () => {
    expect(healthWord(401)).toBe("not signed in");
    expect(healthWord(403)).toBe("not permitted");
    expect(healthWord(500)).toBe("HTTP 500");
    expect(healthWord(404)).toBe("HTTP 404");
    expect(healthWord(0)).toBe("unreachable");
    expect(healthWord(undefined)).toBe("unreachable");
    expect(healthWord("Internal Server Error")).toBe("unreachable");
  });
});
