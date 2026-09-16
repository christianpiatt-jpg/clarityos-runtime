/** #167b -- the sha fence. */
import { describe, it, expect } from "vitest";
import { normSha, shortSha, readCurrency, summaryCurrency, turnCaption, UNSTAMPED_CAPTION } from "../sha";

describe("normSha / shortSha", () => {
  it("\u2605 unknown is not a sha; the caption is seven characters", () => {
    expect(normSha("unknown")).toBeNull();
    expect(normSha(" ABC ")).toBe("abc");
    expect(shortSha("bb23e509ae3cad3156103d3d4fa47caa9974ada5")).toBe("bb23e50");
    expect(shortSha(null)).toBe("unknown");
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
