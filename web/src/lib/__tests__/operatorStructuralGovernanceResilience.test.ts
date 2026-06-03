// Card 64 — Structural governance resilience engine unit tests.
//
// Hand-rolled Card 61 + Card 62 + Card 63 text fixtures cover the
// five spec scenarios: baseline resilience, stable, deteriorating,
// high-pressure, and summary correctness. Tests pin the parsed-
// input pipeline against the derived resilience fields independently
// of any future wording tweaks in upstream cards.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceResilience } from "../operatorStructuralGovernanceResilience";

interface GovFixture {
  level:       string;
  profile:     [string, string, string, string];
  inhibitors?: string[];
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
}

function makeDiff({
  delta, direction, slope, pressure, stability, risk,
  drivers = [], inhibitors = [],
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
    `[Governance Delta Summary]\nStub.`
  );
}

interface StabFixture {
  level:      string;
  coherence:  string;
  integrity:  string;
  drift:      string;
  volatility: string;
}

function makeStab({ level, coherence, integrity, drift, volatility }: StabFixture): string {
  return (
    `=== Structural Governance Stability ===\n\n` +
    `[Stability Level]\n${level}\n\n` +
    `[Governance Coherence]\n${coherence}\n\n` +
    `[Governance Integrity]\n${integrity}\n\n` +
    `[Governance Drift]\n${drift}\n\n` +
    `[Governance Volatility]\n${volatility}\n\n` +
    `[Stabilization Trajectory]\nlow → low → low (stable)\n\n` +
    `[Stability Drivers]\n(none)\n\n` +
    `[Stability Inhibitors]\n(none)\n\n` +
    `[Stability Risks]\n(none)\n\n` +
    `[Stability Reinforcement]\n(none)\n\n` +
    `[Stability Decay]\n(none)\n\n` +
    `[System-Level Stability Summary]\nStub.`
  );
}

describe("Card 64 — buildStructuralGovernanceResilience", () => {
  it("baseline LOW → LOW-MEDIUM emits LOW-MEDIUM resilience with the spec-demo 12 sub-blocks in order", () => {
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
    const stab = makeStab({
      level:      "LOW-MEDIUM",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "moderate",
    });
    const out = buildStructuralGovernanceResilience(gov, diff, stab);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Resilience ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Resilience Level]")).toBeGreaterThan(idx("=== Structural Governance Resilience ==="));
    expect(idx("[Load-Bearing Capacity]")).toBeGreaterThan(idx("[Resilience Level]"));
    expect(idx("[Recovery Strength]")).toBeGreaterThan(idx("[Load-Bearing Capacity]"));
    expect(idx("[Fault Tolerance]")).toBeGreaterThan(idx("[Recovery Strength]"));
    expect(idx("[Pressure Response]")).toBeGreaterThan(idx("[Fault Tolerance]"));
    expect(idx("[Resilience Trajectory]")).toBeGreaterThan(idx("[Pressure Response]"));
    expect(idx("[Resilience Drivers]")).toBeGreaterThan(idx("[Resilience Trajectory]"));
    expect(idx("[Resilience Inhibitors]")).toBeGreaterThan(idx("[Resilience Drivers]"));
    expect(idx("[Resilience Risks]")).toBeGreaterThan(idx("[Resilience Inhibitors]"));
    expect(idx("[Resilience Reinforcement]")).toBeGreaterThan(idx("[Resilience Risks]"));
    expect(idx("[Resilience Decay]")).toBeGreaterThan(idx("[Resilience Reinforcement]"));
    expect(idx("[System-Level Resilience Summary]")).toBeGreaterThan(idx("[Resilience Decay]"));

    // Derived fields per spec demo.
    expect(out).toContain("[Resilience Level]\nLOW-MEDIUM");
    expect(out).toContain("[Load-Bearing Capacity]\nmoderate");
    expect(out).toContain("[Recovery Strength]\npartial");
    expect(out).toContain("[Fault Tolerance]\nweak");
    expect(out).toContain("[Pressure Response]\nmoderate");
    expect(out).toContain("[Resilience Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers list (3 lines per spec demo).
    expect(out).toContain("- improving governance stability");
    expect(out).toContain("- reduced governance drift");
    expect(out).toContain("- improved threshold adherence");

    // Inhibitors list (3 lines: 2 from Card 62 + 1 profile-derived).
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");

    // Risks list (3 lines — note "collapse" wording, not "erosion").
    expect(out).toContain("- governance collapse under pressure");
    expect(out).toContain("- drift reactivation");
    expect(out).toContain("- threshold breach");

    // Reinforcement (3 lines, upper-branch is weak so it drops out).
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");

    // Decay (3 lines).
    expect(out).toContain("- thresholds may weaken under load");
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
  });

  it("stable governance MEDIUM → MEDIUM emits MEDIUM resilience + stable trajectory + no drivers/inhibitors", () => {
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
    const stab = makeStab({
      level:      "MEDIUM",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "low",
    });
    const out = buildStructuralGovernanceResilience(gov, diff, stab);

    expect(out).toContain("[Resilience Level]\nMEDIUM");
    expect(out).toContain("[Resilience Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Load-Bearing Capacity]\nmoderate");
    expect(out).toContain("[Recovery Strength]\npartial");
    expect(out).toContain("[Fault Tolerance]\nmoderate");
    // pressure=low + volatility=low + slope=0 → strong pressure response.
    expect(out).toContain("[Pressure Response]\nstrong");
    expect(out).toContain("[Resilience Drivers]\n(none)");
    expect(out).toContain("[Resilience Inhibitors]\n(none)");
    expect(out).toContain("Governance resilience is steady with no material changes. Recovery strength is partial, and load-bearing capacity is moderate.");
  });

  it("deteriorating resilience MEDIUM → LOW-MEDIUM clamps stability further down with a deteriorating summary", () => {
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
    const stab = makeStab({
      level:      "LOW",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "high",
      volatility: "moderate",
    });
    const out = buildStructuralGovernanceResilience(gov, diff, stab);

    // stability=LOW → resilience LOW (clamped at 0 after slope+drift penalties).
    expect(out).toContain("[Resilience Level]\nLOW");
    expect(out).toContain("[Resilience Trajectory]\nlow-medium → low → low (projected)");
    // Recovery weak: integrity not strong, slope<0, no drivers.
    expect(out).toContain("[Recovery Strength]\nweak");
    expect(out).toContain("[Resilience Drivers]\n(none)");
    // Inhibitors carry over delta + profile-derived weak threshold.
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- incomplete drift containment");
    expect(out).toContain("- partial invariant compliance");
    expect(out).toContain("- weak threshold adherence");
    // Summary uses deteriorating wording.
    expect(out).toContain("Governance resilience is deteriorating under CZ and drift pressure.");
    expect(out).toContain("Recovery strength is weak, and load-bearing capacity is moderate.");
  });

  it("high-pressure scenario: pressure=high + volatility=high → resilience=LOW, pressure response=weak, load capacity=weak", () => {
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
    const stab = makeStab({
      level:      "LOW",
      coherence:  "weak",
      integrity:  "weak",
      drift:      "high",
      volatility: "high",
    });
    const out = buildStructuralGovernanceResilience(gov, diff, stab);

    expect(out).toContain("[Resilience Level]\nLOW");
    expect(out).toContain("[Load-Bearing Capacity]\nweak");
    expect(out).toContain("[Recovery Strength]\nweak");
    expect(out).toContain("[Fault Tolerance]\nweak");
    expect(out).toContain("[Pressure Response]\nweak");
    // High pressure adds volatility spike risk + governance collapse.
    expect(out).toContain("- governance collapse under pressure");
    expect(out).toContain("- volatility spike");
    // All dims weak → reinforcement empty.
    expect(out).toContain("[Resilience Reinforcement]\n(none)");
  });

  it("summary correctness: improving + drift improved + persistent vulnerabilities mirrors the spec demo phrasing exactly", () => {
    // Spec demo:
    //   "Governance resilience is improving but remains vulnerable to
    //    CZ and upper-branch instability. Recovery strength is partial,
    //    and load-bearing capacity is moderate."
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
    const stab = makeStab({
      level:      "LOW-MEDIUM",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "moderate",
    });
    const out = buildStructuralGovernanceResilience(gov, diff, stab);

    expect(out).toContain(
      "Governance resilience is improving but remains vulnerable to CZ and upper-branch instability. Recovery strength is partial, and load-bearing capacity is moderate.",
    );
  });
});
