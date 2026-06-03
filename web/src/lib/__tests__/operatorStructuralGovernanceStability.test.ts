// Card 63 — Structural governance stability engine unit tests.
//
// Hand-rolled Card 61 + Card 62 text fixtures cover the five spec
// scenarios: baseline improvement, stable, deteriorating, high-
// volatility, and summary correctness. Tests pin the parsed-input
// pipeline against the derived stability fields independently of
// any future Card 61 / Card 62 wording tweaks.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceStability } from "../operatorStructuralGovernanceStability";

interface GovFixture {
  level:        string;
  profile:      [string, string, string, string]; // invariant, threshold, upper, vol
  inhibitors?:  string[];
}

function makeGov({ level, profile, inhibitors = [] }: GovFixture): string {
  const inhibitorBody =
    inhibitors.length === 0
      ? "(none)"
      : inhibitors.map((i) => `- ${i}`).join("\n");

  return (
    `=== Structural Governance ===\n\n` +
    `[Governance Level]\n${level}\n\n` +
    `[Structural Invariants]\n- CZ must not exceed 2\n\n` +
    `[Governance Profile]\n` +
    `- ${profile[0]} invariant compliance\n` +
    `- ${profile[1]} threshold adherence\n` +
    `- ${profile[2]} upper-branch containment\n` +
    `- ${profile[3]} volatility control\n\n` +
    `[Governance Trajectory]\nlow → low → low (stable)\n\n` +
    `[Governance Drivers]\n(none)\n\n` +
    `[Governance Inhibitors]\n${inhibitorBody}\n\n` +
    `[Governance Thresholds]\n- CZ < 2\n\n` +
    `[Governance Breach Conditions]\n(none)\n\n` +
    `[Governance Reinforcement]\n(none)\n\n` +
    `[Governance Decay]\n(none)\n\n` +
    `[System-Level Governance Summary]\nStub.`
  );
}

interface DiffFixture {
  delta:       string;
  direction:   string;
  slope:       string;
  pressure:    string;
  stability:   string;
  risk:        string;
  drivers?:    string[];
  inhibitors?: string[];
  summary?:    string;
}

function makeDiff({
  delta, direction, slope, pressure, stability, risk,
  drivers = [], inhibitors = [], summary = "Stub.",
}: DiffFixture): string {
  const dr = drivers.length === 0    ? "(none)" : drivers.map((d) => `- ${d}`).join("\n");
  const ih = inhibitors.length === 0 ? "(none)" : inhibitors.map((i) => `- ${i}`).join("\n");
  return (
    `=== Structural Governance Diff ===\n\n` +
    `[Governance Delta]\n${delta}\n\n` +
    `[Governance Direction]\n${direction}\n\n` +
    `[Governance Slope]\n${slope}\n\n` +
    `[Governance Pressure]\n${pressure}\n\n` +
    `[Governance Stability]\n${stability}\n\n` +
    `[Governance Risk]\n${risk}\n\n` +
    `[Governance Delta Drivers]\n${dr}\n\n` +
    `[Governance Delta Inhibitors]\n${ih}\n\n` +
    `[Governance Delta Summary]\n${summary}`
  );
}

describe("Card 63 — buildStructuralGovernanceStability", () => {
  it("baseline improvement LOW → LOW-MEDIUM emits LOW-MEDIUM stability + improving trajectory + spec-demo block ordering", () => {
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({
      delta:     "LOW → LOW-MEDIUM",
      direction: "improving",
      slope:     "+1",
      pressure:  "moderate",
      stability: "partial",
      risk:      "elevated",
      drivers:    ["improved drift suppression"],
      inhibitors: ["persistent CZ vulnerability", "upper-branch instability"],
    });
    const out = buildStructuralGovernanceStability(gov, diff);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Stability ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Stability Level]")).toBeGreaterThan(idx("=== Structural Governance Stability ==="));
    expect(idx("[Governance Coherence]")).toBeGreaterThan(idx("[Stability Level]"));
    expect(idx("[Governance Integrity]")).toBeGreaterThan(idx("[Governance Coherence]"));
    expect(idx("[Governance Drift]")).toBeGreaterThan(idx("[Governance Integrity]"));
    expect(idx("[Governance Volatility]")).toBeGreaterThan(idx("[Governance Drift]"));
    expect(idx("[Stabilization Trajectory]")).toBeGreaterThan(idx("[Governance Volatility]"));
    expect(idx("[Stability Drivers]")).toBeGreaterThan(idx("[Stabilization Trajectory]"));
    expect(idx("[Stability Inhibitors]")).toBeGreaterThan(idx("[Stability Drivers]"));
    expect(idx("[Stability Risks]")).toBeGreaterThan(idx("[Stability Inhibitors]"));
    expect(idx("[Stability Reinforcement]")).toBeGreaterThan(idx("[Stability Risks]"));
    expect(idx("[Stability Decay]")).toBeGreaterThan(idx("[Stability Reinforcement]"));
    expect(idx("[System-Level Stability Summary]")).toBeGreaterThan(idx("[Stability Decay]"));

    // Derived fields.
    expect(out).toContain("[Stability Level]\nLOW-MEDIUM");
    expect(out).toContain("[Governance Coherence]\npartial");
    expect(out).toContain("[Governance Integrity]\nmoderate");
    expect(out).toContain("[Governance Drift]\nlow");
    expect(out).toContain("[Governance Volatility]\nmoderate");
    expect(out).toContain("[Stabilization Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers: positive slope + drift delta → 3 lines.
    expect(out).toContain("- improving governance slope");
    expect(out).toContain("- reduced drift");
    expect(out).toContain("- improved threshold adherence");

    // Inhibitors: 2 carried over from Card 62 + 1 profile-derived.
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");

    // Risks / Reinforcement / Decay.
    expect(out).toContain("- governance erosion under pressure");
    expect(out).toContain("- drift reactivation");
    expect(out).toContain("- threshold breach");
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");
    expect(out).toContain("- thresholds may weaken under load");
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
  });

  it("stable governance MEDIUM → MEDIUM emits MEDIUM stability + stable trajectory + no drivers/inhibitors", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["moderate", "moderate", "moderate", "moderate"],
    });
    const diff = makeDiff({
      delta:     "MEDIUM → MEDIUM",
      direction: "stable",
      slope:     "0",
      pressure:  "low",
      stability: "partial",
      risk:      "low",
    });
    const out = buildStructuralGovernanceStability(gov, diff);

    expect(out).toContain("[Stability Level]\nMEDIUM");
    expect(out).toContain("[Stabilization Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Governance Coherence]\npartial");
    expect(out).toContain("[Governance Integrity]\nmoderate");
    expect(out).toContain("[Governance Drift]\nlow");
    expect(out).toContain("[Governance Volatility]\nlow");
    expect(out).toContain("[Stability Drivers]\n(none)");
    expect(out).toContain("[Stability Inhibitors]\n(none)");
    expect(out).toContain("Governance stability is steady with no material changes.");
  });

  it("deteriorating stability MEDIUM → LOW-MEDIUM drops one bucket below the governance level with a deteriorating summary", () => {
    const gov = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["partial", "weak", "moderate", "moderate"],
      inhibitors: ["CZ vulnerability", "incomplete drift containment"],
    });
    const diff = makeDiff({
      delta:     "MEDIUM → LOW-MEDIUM",
      direction: "deteriorating",
      slope:     "-1",
      pressure:  "moderate",
      stability: "weak",
      risk:      "high",
      inhibitors: ["persistent CZ vulnerability", "incomplete drift containment"],
    });
    const out = buildStructuralGovernanceStability(gov, diff);

    // LOW-MEDIUM gov - 1 (negative slope) = LOW stability.
    expect(out).toContain("[Stability Level]\nLOW");
    expect(out).toContain("[Stabilization Trajectory]\nlow-medium → low → low (projected)");
    expect(out).toContain("[Governance Drift]\nhigh");
    expect(out).toContain("[Governance Volatility]\nmoderate");
    // Drivers list empty (no positive slope, no delta drivers).
    expect(out).toContain("[Stability Drivers]\n(none)");
    // Inhibitors include carryover + profile-derived weak threshold.
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- incomplete drift containment");
    expect(out).toContain("- partial invariant compliance");
    expect(out).toContain("- weak threshold adherence");
    // Deteriorating summary phrasing.
    expect(out).toContain("Governance stability is deteriorating under CZ and drift pressure.");
    expect(out).toContain("Drift is uncontrolled, but threshold adherence is only partial.");
  });

  it("high-volatility scenario: pressure=high + 4 inhibitors → volatility=high, stability clamped to LOW", () => {
    const gov = makeGov({
      level:   "LOW",
      profile: ["weak", "weak", "weak", "weak"],
      inhibitors: [
        "CZ vulnerability",
        "upper-branch instability",
        "incomplete drift containment",
        "volatility breach",
      ],
    });
    const diff = makeDiff({
      delta:     "LOW-MEDIUM → LOW",
      direction: "deteriorating",
      slope:     "-1",
      pressure:  "high",
      stability: "weak",
      risk:      "high",
      inhibitors: [
        "persistent CZ vulnerability",
        "upper-branch instability",
        "incomplete drift containment",
        "volatility breach",
      ],
    });
    const out = buildStructuralGovernanceStability(gov, diff);

    expect(out).toContain("[Stability Level]\nLOW");
    expect(out).toContain("[Governance Volatility]\nhigh");
    expect(out).toContain("[Governance Drift]\nhigh");
    expect(out).toContain("[Governance Coherence]\nweak");
    expect(out).toContain("[Governance Integrity]\nweak");
    // High-pressure adds volatility spike risk.
    expect(out).toContain("- volatility spike");
    // All 4 maintain lines drop out (every dim is weak, rank 0).
    expect(out).toContain("[Stability Reinforcement]\n(none)");
    // Summary: weak integrity → "invariants are weakly held" clause.
    expect(out).toContain(", and invariants are weakly held.");
  });

  it("summary correctness: improving + drift improved + persistent vulnerabilities mirrors the spec demo phrasing exactly", () => {
    // Spec demo:
    //   "Governance stability is improving but remains vulnerable to
    //    CZ and upper-branch instability. Drift is controlled, but
    //    threshold adherence is only partial."
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({
      delta:     "LOW → LOW-MEDIUM",
      direction: "improving",
      slope:     "+1",
      pressure:  "moderate",
      stability: "partial",
      risk:      "elevated",
      drivers:    ["improved drift suppression"],
      inhibitors: ["persistent CZ vulnerability", "upper-branch instability"],
    });
    const out = buildStructuralGovernanceStability(gov, diff);

    expect(out).toContain(
      "Governance stability is improving but remains vulnerable to CZ and upper-branch instability. Drift is controlled, but threshold adherence is only partial.",
    );
  });
});
