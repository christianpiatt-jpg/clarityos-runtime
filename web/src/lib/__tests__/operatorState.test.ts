// Card 69 — Operator State engine unit tests.
//
// Phase-5 Tier-1. The helper parses `key=value` tokens from a raw
// operator text input; tests cover the five spec scenarios:
// baseline, high-load, high-drift, high-pressure, and summary
// correctness with the spec demo phrasing.

import { describe, expect, it } from "vitest";

import { buildOperatorState } from "../operatorState";

describe("Card 69 — buildOperatorState", () => {
  it("baseline empty input emits HIGH operator level with all-optimal sub-fields + steady summary", () => {
    const out = buildOperatorState("");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator State ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Operator Level]")).toBeGreaterThan(idx("=== Operator State ==="));
    expect(idx("[Operator Load]")).toBeGreaterThan(idx("[Operator Level]"));
    expect(idx("[Operator Drift]")).toBeGreaterThan(idx("[Operator Load]"));
    expect(idx("[Operator Clarity]")).toBeGreaterThan(idx("[Operator Drift]"));
    expect(idx("[Operator Stability]")).toBeGreaterThan(idx("[Operator Clarity]"));
    expect(idx("[Operator Pressure]")).toBeGreaterThan(idx("[Operator Stability]"));
    expect(idx("[Operator Risk]")).toBeGreaterThan(idx("[Operator Pressure]"));
    expect(idx("[Operator Drivers]")).toBeGreaterThan(idx("[Operator Risk]"));
    expect(idx("[Operator Inhibitors]")).toBeGreaterThan(idx("[Operator Drivers]"));
    expect(idx("[Operator Summary]")).toBeGreaterThan(idx("[Operator Inhibitors]"));

    // All-optimal baseline (no tokens parsed → defaults).
    expect(out).toContain("[Operator Level]\nHIGH");
    expect(out).toContain("[Operator Load]\nlow");
    expect(out).toContain("[Operator Drift]\nlow");
    expect(out).toContain("[Operator Clarity]\nstrong");
    expect(out).toContain("[Operator Stability]\nstrong");
    expect(out).toContain("[Operator Pressure]\nlow");
    expect(out).toContain("[Operator Risk]\nlow");
    expect(out).toContain("[Operator Drivers]\n(none)");
    expect(out).toContain("[Operator Inhibitors]\n(none)");
    expect(out).toContain("Operator state is steady. Clarity is strong, drift is low, and stability is strong.");
  });

  it("high-load scenario: load=high triggers load-saturation inhibitor + drops level + moderate risk", () => {
    const out = buildOperatorState("load=high");

    expect(out).toContain("[Operator Load]\nhigh");
    // Score: load=-2 → MEDIUM-HIGH.
    expect(out).toContain("[Operator Level]\nMEDIUM-HIGH");
    // 1 critical state → moderate risk.
    expect(out).toContain("[Operator Risk]\nmoderate");
    // Load-saturation inhibitor fires.
    expect(out).toContain("- load saturation");
    // No drivers fire (direction not improving + load is high).
    expect(out).toContain("[Operator Drivers]\n(none)");
  });

  it("high-drift scenario: drift=high triggers active-drift inhibitor + drops level + moderate risk", () => {
    const out = buildOperatorState("drift=high");

    expect(out).toContain("[Operator Drift]\nhigh");
    // Score: drift=-2 → MEDIUM-HIGH.
    expect(out).toContain("[Operator Level]\nMEDIUM-HIGH");
    expect(out).toContain("[Operator Risk]\nmoderate");
    // "active drift" fires; "residual drift" does NOT (we prefer the
    // active form when drift itself is the trigger).
    expect(out).toContain("- active drift");
    expect(out).not.toContain("- residual drift");
  });

  it("high-pressure scenario: pressure=high triggers high-pressure inhibitor + residual drift + drops level", () => {
    const out = buildOperatorState("pressure=high");

    expect(out).toContain("[Operator Pressure]\nhigh");
    // Score: pressure=-3 → MEDIUM.
    expect(out).toContain("[Operator Level]\nMEDIUM");
    expect(out).toContain("[Operator Risk]\nmoderate");
    // High pressure surfaces both the primary inhibitor and the
    // residual-drift secondary effect.
    expect(out).toContain("- high pressure");
    expect(out).toContain("- residual drift");
    // Summary mentions the deteriorating-style "steady but under
    // elevated pressure" framing because direction defaults to stable.
    expect(out).toContain("Operator state is steady but under elevated pressure.");
  });

  it("summary correctness: improving + load=moderate + clarity=partial + stability=moderate + pressure=elevated mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator state is improving but remains under elevated
    //    pressure. Clarity is partial, drift is low, and stability
    //    is moderate."
    const tokens = "load=moderate drift=low clarity=partial stability=moderate pressure=elevated direction=improving";
    const out    = buildOperatorState(tokens);

    expect(out).toContain("[Operator Level]\nLOW-MEDIUM");
    expect(out).toContain("[Operator Load]\nmoderate");
    expect(out).toContain("[Operator Drift]\nlow");
    expect(out).toContain("[Operator Clarity]\npartial");
    expect(out).toContain("[Operator Stability]\nmoderate");
    expect(out).toContain("[Operator Pressure]\nelevated");
    // 1 critical state (pressure=elevated) → moderate risk.
    expect(out).toContain("[Operator Risk]\nmoderate");

    // Drivers (3 lines per demo).
    expect(out).toContain("- improving clarity");
    expect(out).toContain("- reduced drift");
    expect(out).toContain("- improved load distribution");

    // Inhibitors (3 lines per demo).
    expect(out).toContain("- elevated pressure");
    expect(out).toContain("- partial clarity");
    expect(out).toContain("- residual drift");

    // Exact demo summary.
    expect(out).toContain(
      "Operator state is improving but remains under elevated pressure. Clarity is partial, drift is low, and stability is moderate.",
    );
  });
});
