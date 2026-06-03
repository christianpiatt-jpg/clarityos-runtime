// Card 66 — Structural governance coherence engine unit tests.
//
// Hand-rolled Card 61 + 62 + 63 + 64 + 65 text fixtures cover the
// five spec scenarios: baseline coherence, stable, deteriorating,
// contradiction (stability ≫ immunity), and summary correctness.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceCoherence } from "../operatorStructuralGovernanceCoherence";

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

function makeRes(level: string): string {
  return (
    `=== Structural Governance Resilience ===\n\n` +
    `[Resilience Level]\n${level}\n\n` +
    `[Load-Bearing Capacity]\nmoderate\n\n` +
    `[Recovery Strength]\npartial\n\n` +
    `[Fault Tolerance]\nweak\n\n` +
    `[Pressure Response]\nmoderate\n\n` +
    `[Resilience Trajectory]\nlow → low → low (stable)\n\n` +
    `[Resilience Drivers]\n(none)\n\n` +
    `[Resilience Inhibitors]\n(none)\n\n` +
    `[Resilience Risks]\n(none)\n\n` +
    `[Resilience Reinforcement]\n(none)\n\n` +
    `[Resilience Decay]\n(none)\n\n` +
    `[System-Level Resilience Summary]\nStub.`
  );
}

interface ImmFixture {
  level:          string;
  futureRes:      string;
  hardening:      string;
  vulnerability:  string;
}

function makeImm({ level, futureRes, hardening, vulnerability }: ImmFixture): string {
  return (
    `=== Structural Governance Immunity ===\n\n` +
    `[Immunity Level]\n${level}\n\n` +
    `[Future-Resistance]\n${futureRes}\n\n` +
    `[Governance Hardening]\n${hardening}\n\n` +
    `[Governance Vulnerability]\n${vulnerability}\n\n` +
    `[Immunity Trajectory]\nlow → low → low (stable)\n\n` +
    `[Immunity Drivers]\n(none)\n\n` +
    `[Immunity Inhibitors]\n(none)\n\n` +
    `[Immunity Thresholds]\n- CZ < 2\n\n` +
    `[Immunity Breach Conditions]\n(none)\n\n` +
    `[Immunity Reinforcement]\n(none)\n\n` +
    `[Immunity Decay]\n(none)\n\n` +
    `[Early-Warning Signals]\n(none)\n\n` +
    `[System-Level Immunity Summary]\nStub.`
  );
}

describe("Card 66 — buildStructuralGovernanceCoherence", () => {
  it("baseline LOW → LOW-MEDIUM emits LOW-MEDIUM coherence with all 12 sub-blocks in spec order", () => {
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
    });
    const stab = makeStab({
      level:      "LOW-MEDIUM",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "moderate",
    });
    const res = makeRes("LOW-MEDIUM");
    const imm = makeImm({
      level: "LOW-MEDIUM", futureRes: "moderate", hardening: "partial", vulnerability: "elevated",
    });
    const out = buildStructuralGovernanceCoherence(gov, diff, stab, res, imm);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Coherence ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Coherence Level]")).toBeGreaterThan(idx("=== Structural Governance Coherence ==="));
    expect(idx("[Governance Alignment]")).toBeGreaterThan(idx("[Coherence Level]"));
    expect(idx("[Governance Consistency]")).toBeGreaterThan(idx("[Governance Alignment]"));
    expect(idx("[Cross-Dimension Agreement]")).toBeGreaterThan(idx("[Governance Consistency]"));
    expect(idx("[Contradiction Risk]")).toBeGreaterThan(idx("[Cross-Dimension Agreement]"));
    expect(idx("[Coherence Trajectory]")).toBeGreaterThan(idx("[Contradiction Risk]"));
    expect(idx("[Coherence Drivers]")).toBeGreaterThan(idx("[Coherence Trajectory]"));
    expect(idx("[Coherence Inhibitors]")).toBeGreaterThan(idx("[Coherence Drivers]"));
    expect(idx("[Coherence Risks]")).toBeGreaterThan(idx("[Coherence Inhibitors]"));
    expect(idx("[Coherence Reinforcement]")).toBeGreaterThan(idx("[Coherence Risks]"));
    expect(idx("[Coherence Decay]")).toBeGreaterThan(idx("[Coherence Reinforcement]"));
    expect(idx("[System-Level Coherence Summary]")).toBeGreaterThan(idx("[Coherence Decay]"));

    // Derived fields per spec demo.
    expect(out).toContain("[Coherence Level]\nLOW-MEDIUM");
    expect(out).toContain("[Governance Alignment]\npartial");
    expect(out).toContain("[Governance Consistency]\nmoderate");
    expect(out).toContain("[Cross-Dimension Agreement]\npartial");
    expect(out).toContain("[Contradiction Risk]\nelevated");
    expect(out).toContain("[Coherence Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers (3 lines when slope > 0).
    expect(out).toContain("- improving governance stability");
    expect(out).toContain("- improving governance resilience");
    expect(out).toContain("- improving immunity trajectory");

    // Inhibitors carry over Card 61 wording verbatim (no "persistent").
    expect(out).toContain("- CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");
    expect(out).not.toContain("- persistent CZ vulnerability");

    // Risks (3 lines per spec demo).
    expect(out).toContain("- cross-dimension divergence");
    expect(out).toContain("- threshold misalignment");
    expect(out).toContain("- governance contradiction under pressure");

    // Reinforcement (4 lines: invariant, drift, volatility, hardening;
    // upper-branch=weak so it drops out).
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");
    expect(out).toContain("- maintain governance hardening");
    expect(out).not.toContain("- maintain upper-branch containment");

    // Decay (3 lines in Card 66 order: drift, volatility, thresholds).
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
    expect(out).toContain("- thresholds may weaken under load");
  });

  it("stable coherence MEDIUM → MEDIUM emits MEDIUM coherence + stable trajectory + no drivers/inhibitors", () => {
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
    const res = makeRes("MEDIUM");
    const imm = makeImm({
      level: "MEDIUM", futureRes: "moderate", hardening: "partial", vulnerability: "low",
    });
    const out = buildStructuralGovernanceCoherence(gov, diff, stab, res, imm);

    expect(out).toContain("[Coherence Level]\nMEDIUM");
    expect(out).toContain("[Coherence Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Governance Alignment]\npartial");
    expect(out).toContain("[Cross-Dimension Agreement]\nstrong");
    expect(out).toContain("[Contradiction Risk]\nlow");
    expect(out).toContain("[Coherence Drivers]\n(none)");
    expect(out).toContain("[Coherence Inhibitors]\n(none)");
    expect(out).toContain("Governance coherence is steady with no material changes. Alignment is partial, and cross-dimension agreement is strong.");
  });

  it("deteriorating coherence MEDIUM → LOW-MEDIUM drops the floor with a deteriorating summary", () => {
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
    });
    const stab = makeStab({
      level:      "LOW",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "high",
      volatility: "moderate",
    });
    const res = makeRes("LOW");
    const imm = makeImm({
      level: "LOW", futureRes: "weak", hardening: "partial", vulnerability: "high",
    });
    const out = buildStructuralGovernanceCoherence(gov, diff, stab, res, imm);

    // min(LOW, LOW, LOW)=0 → LOW (further decremented by weak threshold).
    expect(out).toContain("[Coherence Level]\nLOW");
    // vulnerability=high → contradiction=high.
    expect(out).toContain("[Contradiction Risk]\nhigh");
    expect(out).toContain("[Coherence Trajectory]\nlow-medium → low → low (projected)");
    expect(out).toContain("[Coherence Drivers]\n(none)");
    expect(out).toContain("Governance coherence is deteriorating under CZ and drift pressure.");
  });

  it("contradiction scenario: stability/resilience HIGH but immunity LOW → contradiction=high, alignment=weak", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "partial"],
    });
    const diff = makeDiff({
      delta:     "LOW-MEDIUM → MEDIUM",
      direction: "improving",
      slope:     "+1",
      pressure:  "low",
      stability: "partial",
      risk:      "low",
    });
    const stab = makeStab({
      level:      "MEDIUM-HIGH",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "low",
    });
    const res = makeRes("MEDIUM-HIGH");
    const imm = makeImm({
      level: "LOW", futureRes: "weak", hardening: "partial", vulnerability: "high",
    });
    const out = buildStructuralGovernanceCoherence(gov, diff, stab, res, imm);

    // stability=3, resilience=3, immunity=0 → spread=3 → alignment=weak.
    expect(out).toContain("[Governance Alignment]\nweak");
    // gov=2, stab=3, res=3, imm=0 → spread=3 → agreement=weak.
    expect(out).toContain("[Cross-Dimension Agreement]\nweak");
    // vulnerability=high → contradiction=high.
    expect(out).toContain("[Contradiction Risk]\nhigh");
    // min(3,3,0) = 0 → LOW (no extra decrements: 1 inhibitor, threshold not weak).
    expect(out).toContain("[Coherence Level]\nLOW");
    // Risks fire because layerSpread >= 1 + threshold moderate + contradiction high.
    expect(out).toContain("- cross-dimension divergence");
    expect(out).toContain("- governance contradiction under pressure");
  });

  it("summary correctness: baseline improving + 3 inhibitors mirrors the spec demo phrasing", () => {
    // Spec demo:
    //   "Governance coherence is improving but remains vulnerable to
    //    CZ and upper-branch instability. Alignment is partial, and
    //    cross-dimension agreement is moderate."
    // (Note: agreement block is "partial", summary maps to "moderate".)
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
    });
    const stab = makeStab({
      level:      "LOW-MEDIUM",
      coherence:  "partial",
      integrity:  "moderate",
      drift:      "low",
      volatility: "moderate",
    });
    const res = makeRes("LOW-MEDIUM");
    const imm = makeImm({
      level: "LOW-MEDIUM", futureRes: "moderate", hardening: "partial", vulnerability: "elevated",
    });
    const out = buildStructuralGovernanceCoherence(gov, diff, stab, res, imm);

    expect(out).toContain(
      "Governance coherence is improving but remains vulnerable to CZ and upper-branch instability. Alignment is partial, and cross-dimension agreement is moderate.",
    );
  });
});
