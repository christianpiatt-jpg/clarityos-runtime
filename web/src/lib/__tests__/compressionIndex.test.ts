/**
 * compressionIndex — CI = 1 − H/H_max over an attractor distribution.
 *
 * ★ WHAT THESE PIN. Three REAL captured reads, asserted to 4 dp, plus the
 * two edges that would otherwise produce NaN. And the reading that started
 * this: a flat distribution is CI = 0 and the word for it is "resilient" —
 * a measurement, not a non-result.
 *
 * ★ FIXTURE 3 — the brief said 23/23/32/23 → 0.0081. Under the brief's own
 * rule (normalise by the sum FIRST) the value is 0.008151, which rounds to
 * 0.0082; 0.0081 is that number TRUNCATED. toBeCloseTo(0.0081, 4) fails its
 * 5e-05 threshold by ~6e-07 (|0.008151 - 0.0081| = 5.06e-05). This asserts
 * what the rule produces, at 4 dp and at 6 dp, and
 * the discrepancy is reported rather than absorbed.
 */
import { describe, it, expect } from "vitest";

import { compressionIndex, compressionWord } from "../compressionIndex";

function ci(dist: number[]) {
  const r = compressionIndex(dist);
  if (r.kind !== "ci") throw new Error("expected a CI, got " + r.kind);
  return r;
}

describe("compressionIndex — the three captured reads (4 dp)", () => {
  it("25/25/25/25 → 0.0000 (flat: H == H_max)", () => {
    const r = ci([25, 25, 25, 25]);
    expect(r.ci).toBeCloseTo(0.0, 4);
    expect(r.h).toBeCloseTo(r.hMax, 6);
    expect(r.n).toBe(4);
  });

  it("23.5/23.5/29.5/23.5 → 0.0038", () => {
    expect(ci([23.5, 23.5, 29.5, 23.5]).ci).toBeCloseTo(0.0038, 4);
  });

  it("23/23/32/23 (sums to 101) → 0.008151, i.e. 0.0082 at 4 dp", () => {
    const r = ci([23, 23, 32, 23]);
    expect(r.ci).toBeCloseTo(0.008151, 6);
    expect(r.ci).toBeCloseTo(0.0082, 4);
    // and NOT the brief's truncated figure
    expect(Math.abs(r.ci - 0.0081)).toBeGreaterThan(0.00005);
  });
});

describe("compressionIndex — the rule", () => {
  it("normalises by the sum first: scale does not change CI", () => {
    const a = ci([23, 23, 32, 23]).ci;
    const b = ci([230, 230, 320, 230]).ci;
    expect(a).toBeCloseTo(b, 10);
  });

  it("n is the attractors PRESENT in the payload, not a hard-coded 4", () => {
    expect(ci([50, 50]).n).toBe(2);
    expect(ci([50, 50]).hMax).toBeCloseTo(Math.log(2), 10);
    expect(ci([10, 10, 10]).n).toBe(3);
  });

  it("a zero-weight attractor is present and zero: it widens H_max but adds nothing to H", () => {
    // One attractor holds everything: H = 0, H_max = ln 4, CI = 1.
    const r = ci([100, 0, 0, 0]);
    expect(r.n).toBe(4);
    expect(r.h).toBeCloseTo(0, 10);
    expect(r.ci).toBeCloseTo(1, 10);
    expect(compressionWord(r.ci)).toBe("brittle");
  });

  it("skips p ≤ 0 in the sum — never ln(0), never NaN", () => {
    const r = ci([0, 60, 40, 0]);
    expect(Number.isFinite(r.ci)).toBe(true);
    expect(Number.isFinite(r.h)).toBe(true);
  });
});

describe("compressionIndex — D5: no basis is a different KIND", () => {
  it("n ≤ 1 → sentinel, never NaN", () => {
    expect(compressionIndex([100])).toEqual({ kind: "none", n: 1, reason: "single_attractor" });
    expect(compressionIndex([])).toEqual({ kind: "none", n: 0, reason: "single_attractor" });
  });

  it("Σw ≤ 0 → sentinel, never NaN", () => {
    expect(compressionIndex([0, 0, 0, 0])).toEqual({ kind: "none", n: 4, reason: "no_weight" });
  });

  it("no branch returns NaN", () => {
    for (const d of [[100], [], [0, 0], [25, 25, 25, 25], [1, 0, 0]]) {
      const r = compressionIndex(d);
      if (r.kind === "ci") {
        expect(Number.isNaN(r.ci)).toBe(false);
        expect(Number.isNaN(r.h)).toBe(false);
      }
    }
  });
});

describe("compressionWord — the boundaries as ruled", () => {
  it("< 0.1 resilient · 0.1–0.5 leaning · > 0.5 brittle", () => {
    expect(compressionWord(0)).toBe("resilient");
    expect(compressionWord(0.0999)).toBe("resilient");
    expect(compressionWord(0.1)).toBe("leaning");
    expect(compressionWord(0.5)).toBe("leaning");
    expect(compressionWord(0.5001)).toBe("brittle");
    expect(compressionWord(1)).toBe("brittle");
  });

  it("★ a flat reading is resilient — the reading that started this rail", () => {
    expect(compressionWord(ci([25, 25, 25, 25]).ci)).toBe("resilient");
  });
});
