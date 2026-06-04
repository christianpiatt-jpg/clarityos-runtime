// Card 70 — Operator State Diff engine unit tests.
//
// Builds operator-state inputs via the Card 69 helper directly so
// the test fixtures stay tied to the canonical state output. Tests
// cover the five spec scenarios: baseline diff, high-drift delta,
// high-pressure delta, improving clarity, and summary correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState } from "../operatorState";
import { buildOperatorDiff }  from "../operatorStateDiff";

describe("Card 70 — buildOperatorDiff", () => {
  it("baseline (prev = curr = empty inputs) emits HIGH slope + all-stable deltas + no drivers/inhibitors", () => {
    const prev = buildOperatorState("");
    const curr = buildOperatorState("");
    const out  = buildOperatorDiff(prev, curr);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Diff ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Operator Slope]")).toBeGreaterThan(idx("=== Operator Diff ==="));
    expect(idx("[Drift Delta]")).toBeGreaterThan(idx("[Operator Slope]"));
    expect(idx("[Clarity Delta]")).toBeGreaterThan(idx("[Drift Delta]"));
    expect(idx("[Load Delta]")).toBeGreaterThan(idx("[Clarity Delta]"));
    expect(idx("[Pressure Delta]")).toBeGreaterThan(idx("[Load Delta]"));
    expect(idx("[Stability Delta]")).toBeGreaterThan(idx("[Pressure Delta]"));
    expect(idx("[Risk Delta]")).toBeGreaterThan(idx("[Stability Delta]"));
    expect(idx("[Operator Diff Drivers]")).toBeGreaterThan(idx("[Risk Delta]"));
    expect(idx("[Operator Diff Inhibitors]")).toBeGreaterThan(idx("[Operator Diff Drivers]"));
    expect(idx("[Operator Diff Summary]")).toBeGreaterThan(idx("[Operator Diff Inhibitors]"));

    // All-stable baseline.
    expect(out).toContain("[Operator Slope]\nHIGH");
    expect(out).toContain("[Drift Delta]\nlow");
    expect(out).toContain("[Clarity Delta]\nstrong");
    expect(out).toContain("[Load Delta]\nlow");
    expect(out).toContain("[Pressure Delta]\nlow");
    expect(out).toContain("[Stability Delta]\nstrong");
    expect(out).toContain("[Risk Delta]\nlow");
    expect(out).toContain("[Operator Diff Drivers]\n(none)");
    expect(out).toContain("[Operator Diff Inhibitors]\n(none)");
    expect(out).toContain("Operator trajectory is steady. Drift is low, clarity is steady, and stability is steady.");
  });

  it("high-drift delta: prev baseline → curr drift=high reports high drift delta + deteriorating trajectory", () => {
    const prev = buildOperatorState("");
    const curr = buildOperatorState("drift=high");
    const out  = buildOperatorDiff(prev, curr);

    expect(out).toContain("[Drift Delta]\nhigh");
    // curr operator level = MEDIUM-HIGH; slope mirrors current level.
    expect(out).toContain("[Operator Slope]\nMEDIUM-HIGH");
    // prev=HIGH → curr=MEDIUM-HIGH → direction deteriorating.
    expect(out).toContain("Operator trajectory is deteriorating.");
    // Active-drift inhibitor carries over from Card 69's curr state.
    expect(out).toContain("- active drift");
  });

  it("high-pressure delta: prev baseline → curr pressure=high reports high pressure delta + deteriorating", () => {
    const prev = buildOperatorState("");
    const curr = buildOperatorState("pressure=high");
    const out  = buildOperatorDiff(prev, curr);

    expect(out).toContain("[Pressure Delta]\nhigh");
    // pressure=-3 in Card 69 → score -3 → MEDIUM level → slope MEDIUM.
    expect(out).toContain("[Operator Slope]\nMEDIUM");
    // High pressure phrasing in summary.
    expect(out).toContain("Operator trajectory is deteriorating under high pressure.");
    // High-pressure inhibitor + residual-drift secondary carry over.
    expect(out).toContain("- high pressure");
    expect(out).toContain("- residual drift");
  });

  it("improving clarity: prev clarity=weak → curr clarity=partial reports moderate clarity delta + improving direction", () => {
    // Operator level must actually improve for the direction signal
    // to fire (deltas alone aren't enough — we compare levels).
    // prev: clarity=weak + load=high → score -4 → MEDIUM
    // curr: clarity=partial               → score -1 → MEDIUM-HIGH
    const prev = buildOperatorState("clarity=weak load=high");
    const curr = buildOperatorState("clarity=partial direction=improving");
    const out  = buildOperatorDiff(prev, curr);

    expect(out).toContain("[Clarity Delta]\nmoderate");
    // Slope = curr level = MEDIUM-HIGH.
    expect(out).toContain("[Operator Slope]\nMEDIUM-HIGH");
    // Improving direction phrase + clarity-improving in s2.
    expect(out).toContain("Operator trajectory is improving.");
    expect(out).toContain("clarity is improving");
    // Card 69 emitted "improving clarity" + "improved load distribution"
    // drivers (direction=improving + clarity!=weak + load!=high).
    expect(out).toContain("- improving clarity");
    expect(out).toContain("- improved load distribution");
  });

  it("summary correctness: improving + pressure=elevated mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator trajectory is improving but remains under elevated
    //    pressure. Drift is low, clarity is improving, and stability
    //    is partially increasing."
    // Engineer prev/curr so the level actually moves up (prev=LOW,
    // curr=LOW-MEDIUM) and direction registers as improving.
    const prev = buildOperatorState("clarity=weak stability=weak load=high drift=high");
    const curr = buildOperatorState(
      "load=moderate drift=low clarity=partial stability=moderate pressure=elevated direction=improving",
    );
    const out = buildOperatorDiff(prev, curr);

    expect(out).toContain("[Drift Delta]\nlow");
    expect(out).toContain("[Clarity Delta]\nmoderate");
    expect(out).toContain("[Stability Delta]\npartial");
    expect(out).toContain("[Pressure Delta]\nelevated");
    expect(out).toContain(
      "Operator trajectory is improving but remains under elevated pressure. Drift is low, clarity is improving, and stability is partially increasing.",
    );
    // Drivers + inhibitors carry over Card 69's spec-demo wording.
    expect(out).toContain("- improving clarity");
    expect(out).toContain("- reduced drift");
    expect(out).toContain("- improved load distribution");
    expect(out).toContain("- elevated pressure");
    expect(out).toContain("- partial clarity");
    expect(out).toContain("- residual drift");
  });
});
