/**
 * summaryCurrency — the summary box says whether it still describes the thread.
 *
 * ★ WHAT THESE PIN. The rule is derived from two timestamps the meta already
 * carries. What can go wrong is not the comparison — it is the units (the
 * vault writes ms today, older rows carried seconds), and the two edges where
 * a naive rule would claim "current" for something it cannot measure. A false
 * "current" is the only reading that hides something, so every unmeasurable
 * case must resolve AWAY from it.
 */
import { describe, it, expect } from "vitest";

import { summaryCurrency, toMs, normSha, shortSha } from "../summaryCurrency";

const S = 1_700_000_000;          // a plausible epoch in SECONDS
const MS = S * 1000;              // the same instant in MILLISECONDS

describe("toMs — units by magnitude", () => {
  it("passes milliseconds through and scales seconds up", () => {
    expect(toMs(MS)).toBe(MS);
    expect(toMs(S)).toBe(MS);
  });
  it("returns null for nothing, zero, negatives and non-finite", () => {
    for (const v of [null, undefined, 0, -5, NaN, Infinity]) expect(toMs(v as never)).toBeNull();
  });
});

describe("summaryCurrency", () => {
  it("is CURRENT when the summary was computed at or after the last change", () => {
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS + 10, updated_at: MS })).toBe("current");
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS, updated_at: MS })).toBe("current");
  });

  it("is STALE when the thread moved after the summary", () => {
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS, updated_at: MS + 1 })).toBe("stale");
  });

  it("★ the 2026-09-02 case: a summary computed hours before later turns is stale", () => {
    const threeHoursAgo = MS - 3 * 3600 * 1000;
    expect(summaryCurrency({ summary: "I need to be direct: I can't help with this.",
                             summary_ts_ms: threeHoursAgo, updated_at: MS })).toBe("stale");
  });

  it("mixed units never read as stale by accident of scale", () => {
    // updated_at in SECONDS, summary in MS, same instant → current, not stale.
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS, updated_at: S })).toBe("current");
    // and the reverse pairing
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS + 5, updated_at: S })).toBe("current");
  });

  it("D5 — no summary is NONE, a different kind from stale", () => {
    expect(summaryCurrency({ summary: null, summary_ts_ms: MS, updated_at: MS })).toBe("none");
    expect(summaryCurrency({ summary: "", summary_ts_ms: MS, updated_at: MS })).toBe("none");
    expect(summaryCurrency(null)).toBe("none");
  });

  it("an unmeasurable pair resolves to STALE, never to a false current", () => {
    expect(summaryCurrency({ summary: "s", summary_ts_ms: null, updated_at: MS })).toBe("stale");
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS, updated_at: null })).toBe("stale");
  });
});


// ---------------------------------------------------------------------------
// #127 — the code axis. "Current" needs the time axis AND the code axis.
// ---------------------------------------------------------------------------
// ★ WHAT THESE PIN. A summary made by an older summarizer on a thread nobody
// touched since satisfied the time axis and read cyan. It cannot any more.
// And the enforced path resolves every unmeasurable case AWAY from current:
// no sha on the row, no sha from /health, or /health reporting "unknown".
const SHA_A = "ccbf619ac3dca31a964146537b8fb14c963ed914";
const SHA_B = "9ff057ac2725463999cfed7c38f72f402fc0d26f";
const fresh = (extra: object) => ({ summary: "s", summary_ts_ms: MS, updated_at: MS, ...extra });

describe("normSha / shortSha", () => {
  it("normalises case and whitespace, and refuses the literal unknown", () => {
    expect(normSha("  CCBF619A ")).toBe("ccbf619a");
    expect(normSha("unknown")).toBeNull();
    expect(normSha("")).toBeNull();
    expect(normSha(null)).toBeNull();
  });
  it("shortSha is seven characters, or the word unknown", () => {
    expect(shortSha(SHA_A)).toBe("ccbf619");
    expect(shortSha(null)).toBe("unknown");
    expect(shortSha("unknown")).toBe("unknown");
  });
});

describe("summaryCurrency — the code axis", () => {
  it("(c) same time, same sha → current", () => {
    expect(summaryCurrency(fresh({ summary_commit_sha: SHA_A }), SHA_A)).toBe("current");
  });

  it("(d) ★ same time, OLDER sha → stale: the thread did not move, the code did", () => {
    expect(summaryCurrency(fresh({ summary_commit_sha: SHA_A }), SHA_B)).toBe("stale");
  });

  it("(e) no sha on the row → stale, never current", () => {
    expect(summaryCurrency(fresh({}), SHA_A)).toBe("stale");
    expect(summaryCurrency(fresh({ summary_commit_sha: null }), SHA_A)).toBe("stale");
  });

  it("no live sha (backend unreachable, or /health says unknown) → stale", () => {
    expect(summaryCurrency(fresh({ summary_commit_sha: SHA_A }), null)).toBe("stale");
    expect(summaryCurrency(fresh({ summary_commit_sha: SHA_A }), "unknown")).toBe("stale");
  });

  it("sha comparison is case- and whitespace-insensitive", () => {
    expect(summaryCurrency(fresh({ summary_commit_sha: SHA_A.toUpperCase() }), " " + SHA_A)).toBe("current");
  });

  it("the time axis still wins first: moved thread + matching sha → stale", () => {
    expect(summaryCurrency({ summary: "s", summary_ts_ms: MS, updated_at: MS + 1,
                             summary_commit_sha: SHA_A }, SHA_A)).toBe("stale");
  });

  it("D5 — none is still none, whatever the shas say", () => {
    expect(summaryCurrency({ summary: null, summary_commit_sha: SHA_A }, SHA_A)).toBe("none");
  });

  it("★ backward compatibility: with NO live sha argument the time axis alone decides", () => {
    // The pre-#127 rule, kept for callers with nothing to compare against.
    // The panel never takes this path -- it always passes the live sha.
    expect(summaryCurrency(fresh({}))).toBe("current");
  });
});
