/**
 * #190 -- the summary card's currency is read in TURNS, on two axes, with
 * NO clock: fresh (both hold) · aged (one broke) · old (both broke, or no
 * stamp). "none" is a different kind (no summary). readCurrency is the one
 * verdict every read-back reuses; toMs is a stamp formatter's helper and
 * never touches the verdict.
 */
import { describe, it, expect } from "vitest";
import {
  readCurrency, summaryCurrency, turnCaption, toMs, normSha, shortSha, normTurn,
} from "../summaryCurrency";

const SHA = "abc1234def5678";

describe("readCurrency -- three states, no clock", () => {
  it("★ fresh: made at this turn, by this code", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: SHA, live_sha: SHA })).toBe("fresh");
  });
  it("★ aged: the thread moved one turn (sha still equal)", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 4, made_sha: SHA, live_sha: SHA })).toBe("aged");
  });
  it("★ aged: same turn, the code moved", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: SHA, live_sha: "fffffff0000" })).toBe("aged");
  });
  it("★ old: both broke", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 9, made_sha: SHA, live_sha: "fffffff0000" })).toBe("old");
  });
  it("old: no stamp at all (a row that predates #139), whatever the sha says", () => {
    expect(readCurrency({ made_turn: null, now_turn: 3, made_sha: null, live_sha: SHA })).toBe("old");
    expect(readCurrency({})).toBe("old");
    expect(readCurrency(null)).toBe("old");
  });
  it("★ no turn stamp -> old even when the sha matches (the brief: no stamp -> old); a missing sha with a matching turn is aged", () => {
    expect(readCurrency({ made_turn: undefined, now_turn: 3, made_sha: SHA, live_sha: SHA })).toBe("old");
    expect(readCurrency({ made_turn: null, now_turn: 3, made_sha: SHA, live_sha: SHA })).toBe("old");
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: null, live_sha: SHA })).toBe("aged");
  });
  it("\"unknown\" is not a sha; a non-integer or negative turn is not a stamp", () => {
    expect(readCurrency({ made_turn: 3, now_turn: 3, made_sha: "unknown", live_sha: "unknown" })).toBe("aged");
    expect(readCurrency({ made_turn: 2.5, now_turn: 2.5, made_sha: SHA, live_sha: SHA })).toBe("old");   // not a stamp -> no stamp -> old
    expect(normTurn(-1)).toBeNull();
    expect(normTurn(0)).toBe(0);
  });
  it("sha comparison is case- and whitespace-insensitive", () => {
    expect(readCurrency({ made_turn: 1, now_turn: 1, made_sha: " ABC1234DEF5678 ", live_sha: SHA })).toBe("fresh");
  });
});

describe("summaryCurrency -- the card's wrapper", () => {
  it("D5 -- no summary is NONE, a different kind from old", () => {
    expect(summaryCurrency({ summary: null, summary_turn: 3, message_count: 3, summary_commit_sha: SHA }, SHA)).toBe("none");
    expect(summaryCurrency(null, SHA)).toBe("none");
  });
  it("★ reads summary_turn against message_count and the two shas", () => {
    expect(summaryCurrency({ summary: "s", summary_turn: 3, message_count: 3, summary_commit_sha: SHA }, SHA)).toBe("fresh");
    expect(summaryCurrency({ summary: "s", summary_turn: 3, message_count: 5, summary_commit_sha: SHA }, SHA)).toBe("aged");
    expect(summaryCurrency({ summary: "s", summary_turn: 3, message_count: 5, summary_commit_sha: "0000000" }, SHA)).toBe("old");
  });
  it("★ NO CLOCK: the timestamps change nothing -- a summary stamped hours before the last change is still fresh at its turn", () => {
    const a = summaryCurrency({ summary: "s", summary_turn: 3, message_count: 3, summary_commit_sha: SHA,
                                summary_ts_ms: 1_000, updated_at: 9_999_999_999_999 }, SHA);
    const b = summaryCurrency({ summary: "s", summary_turn: 3, message_count: 3, summary_commit_sha: SHA,
                                summary_ts_ms: 9_999_999_999_999, updated_at: 1_000 }, SHA);
    expect(a).toBe("fresh");
    expect(b).toBe("fresh");
  });
  it("no live sha (backend unreachable, or /health says unknown) -> at best aged", () => {
    expect(summaryCurrency({ summary: "s", summary_turn: 3, message_count: 3, summary_commit_sha: SHA }, null)).toBe("aged");
    expect(summaryCurrency({ summary: "s", summary_turn: 3, message_count: 3, summary_commit_sha: SHA }, "unknown")).toBe("aged");
  });
});

describe("turnCaption / helpers", () => {
  it("made turn a · now turn b; no made stamp reads a dash", () => {
    expect(turnCaption({ made_turn: 3, now_turn: 5 })).toBe("made turn 3 · now turn 5");
    expect(turnCaption({ made_turn: null, now_turn: 5 })).toBe("made turn — · now turn 5");
    expect(turnCaption(null)).toBe("made turn — · now turn —");
  });
  it("toMs is a formatter's helper: units by magnitude, null for nothing", () => {
    expect(toMs(1_700_000_000)).toBe(1_700_000_000_000);
    expect(toMs(1_700_000_000_000)).toBe(1_700_000_000_000);
    expect(toMs(0)).toBeNull();
    expect(toMs(null)).toBeNull();
  });
  it("normSha / shortSha", () => {
    expect(normSha(" ABC ")).toBe("abc");
    expect(normSha("unknown")).toBeNull();
    expect(shortSha(SHA)).toBe("abc1234");
    expect(shortSha(null)).toBe("unknown");
  });
});
