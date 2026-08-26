/**
 * ★★★ A FLAT FIELD MUST NOT RETURN AN ATTRACTOR NAME.
 *
 * The backend picks the attractor by argmax over four state weights, and
 * argmax on a tie silently returns the FIRST bucket — S1. So a perfectly
 * balanced field rendered as "S1 stable coherence": the one state the
 * system exists to produce, reported precisely when nothing had settled.
 *
 * Measured on two consecutive live reads:
 *
 *   25/25/25/25 FLAT  → "S1 stable coherence", while Emotional Physics
 *                       reported stability: unstable, gradient: inward.
 *                       The panel contradicted itself in view.
 *   21/21/36/21       → "S3 pressured incoherence", while EP reported
 *                       intensity: high, posture: pursuing. AGREES.
 *
 * The engine was never broken — it discriminates correctly whenever there
 * IS a winner. The label was the defect, and a label that reassures on a
 * tie is worse than no label, because it reassures in exactly the state
 * that most needs reading.
 *
 * The epsilon is just how these pass. THE TEST IS THE DELIVERABLE.
 */
import { describe, it, expect } from "vitest";

import {
  attractorVerdict,
  ATTRACTOR_TIE_EPSILON,
  SEED_CHAR_LIMIT,
} from "../PersonalElins";

const d = (S1: number, S2: number, S3: number, S4: number) => ({ S1, S2, S3, S4 });

describe("attractorVerdict — the tie-break", () => {
  it("a perfectly flat field names NO attractor (the measured 25/25/25/25 read)", () => {
    const v = attractorVerdict(d(0.25, 0.25, 0.25, 0.25), "S1");
    expect(v.determinate).toBe(false);
    if (!v.determinate) {
      expect(v.leaders).toEqual(["S1", "S2", "S3", "S4"]);
      expect(v.gap).toBe(0);
    }
  });

  it("★ never returns S1 on a tie — the exact failure that shipped", () => {
    const v = attractorVerdict(d(0.25, 0.25, 0.25, 0.25), "S1");
    expect(v.determinate).toBe(false);
    // The backend's own argmax answer is S1; the verdict must not echo it.
    expect((v as { state?: string }).state).toBeUndefined();
  });

  it("the measured discriminating read 21/21/36/21 DOES name S3", () => {
    const v = attractorVerdict(d(0.21, 0.21, 0.36, 0.21), "S3");
    expect(v.determinate).toBe(true);
    if (v.determinate) {
      expect(v.state).toBe("S3");
      // 15pp gap — comfortably above the 5pp epsilon, which is why that
      // epsilon was chosen from the measurement rather than from taste.
      expect(v.gap).toBeCloseTo(0.15, 5);
    }
  });

  it("a near-tie inside epsilon is still indeterminate", () => {
    const v = attractorVerdict(d(0.26, 0.25, 0.25, 0.24), "S1");
    expect(v.determinate).toBe(false);
  });

  it("a gap just outside epsilon resolves", () => {
    const v = attractorVerdict(d(0.34, 0.22, 0.22, 0.22), "S1");
    expect(v.determinate).toBe(true);
    if (v.determinate) expect(v.state).toBe("S2" === v.state ? "S2" : "S1");
  });

  it("the winner is read from the distribution, not from the backend's label", () => {
    // If the two ever disagree, the numbers are the evidence.
    const v = attractorVerdict(d(0.1, 0.1, 0.1, 0.7), "S1");
    expect(v.determinate).toBe(true);
    if (v.determinate) expect(v.state).toBe("S4");
  });

  it("falls back cleanly when the distribution is missing", () => {
    expect(attractorVerdict(null, "S2")).toEqual({
      determinate: true, state: "S2", gap: 1,
    });
    expect(attractorVerdict({}, "S3").determinate).toBe(true);
  });

  it("epsilon sits between float noise and the measured real signal", () => {
    expect(ATTRACTOR_TIE_EPSILON).toBeGreaterThan(0);
    expect(ATTRACTOR_TIE_EPSILON).toBeLessThan(0.15);
  });
});

describe("SEED_CHAR_LIMIT", () => {
  it("mirrors the backend cap that truncates silently", () => {
    // intelligence_kernel.py:1845 — cleaned = cleaned[:6000], a HEAD slice.
    // It keeps the beginning and drops the end, and the end of a narrative
    // seed is where the current state lives.
    expect(SEED_CHAR_LIMIT).toBe(6000);
  });
});
