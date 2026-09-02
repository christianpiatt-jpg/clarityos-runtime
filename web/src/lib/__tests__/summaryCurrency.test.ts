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

import { summaryCurrency, toMs } from "../summaryCurrency";

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
