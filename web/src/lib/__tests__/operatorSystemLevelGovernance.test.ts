// Card 68 — System-Level Governance engine unit tests.
//
// Hand-rolled Card 61 + 62 + 63 + 64 + 65 + 66 + 67 text fixtures
// cover the five spec scenarios: baseline, stable, deteriorating,
// cross-layer contradiction, and summary correctness. Phase-4
// capstone — verifies the whole stack collapses into a single
// integrated state.

import { describe, expect, it } from "vitest";

import { buildSystemLevelGovernance } from "../operatorSystemLevelGovernance";

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
  direction: string;
  slope:     string;
  pressure:  string;
}

function makeDiff({ direction, slope, pressure }: DiffFixture): string {
  return (
    `=== Structural Governance Diff ===\n\n` +
    `[Governance Delta]\nLOW → LOW\n\n` +
    `[Governance Direction]\n${direction}\n\n` +
    `[Governance Slope]\n${slope}\n\n` +
    `[Governance Pressure]\n${pressure}\n\n` +
    `[Governance Stability]\npartial\n\n` +
    `[Governance Risk]\nlow\n\n` +
    `[Governance Delta Drivers]\n(none)\n\n` +
    `[Governance Delta Inhibitors]\n(none)\n\n` +
    `[Governance Delta Summary]\nStub.`
  );
}

interface StabFixture {
  level:     string;
  integrity: string;
}

function makeStab({ level, integrity }: StabFixture): string {
  return (
    `=== Structural Governance Stability ===\n\n` +
    `[Stability Level]\n${level}\n\n` +
    `[Governance Coherence]\npartial\n\n` +
    `[Governance Integrity]\n${integrity}\n\n` +
    `[Governance Drift]\nlow\n\n` +
    `[Governance Volatility]\nlow\n\n` +
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
  level:     string;
  hardening: string;
}

function makeImm({ level, hardening }: ImmFixture): string {
  return (
    `=== Structural Governance Immunity ===\n\n` +
    `[Immunity Level]\n${level}\n\n` +
    `[Future-Resistance]\nmoderate\n\n` +
    `[Governance Hardening]\n${hardening}\n\n` +
    `[Governance Vulnerability]\nelevated\n\n` +
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

interface CohFixture {
  level:         string;
  alignment:     string;
  contradiction: string;
}

function makeCoh({ level, alignment, contradiction }: CohFixture): string {
  return (
    `=== Structural Governance Coherence ===\n\n` +
    `[Coherence Level]\n${level}\n\n` +
    `[Governance Alignment]\n${alignment}\n\n` +
    `[Governance Consistency]\nmoderate\n\n` +
    `[Cross-Dimension Agreement]\npartial\n\n` +
    `[Contradiction Risk]\n${contradiction}\n\n` +
    `[Coherence Trajectory]\nlow → low → low (stable)\n\n` +
    `[Coherence Drivers]\n(none)\n\n` +
    `[Coherence Inhibitors]\n(none)\n\n` +
    `[Coherence Risks]\n(none)\n\n` +
    `[Coherence Reinforcement]\n(none)\n\n` +
    `[Coherence Decay]\n(none)\n\n` +
    `[System-Level Coherence Summary]\nStub.`
  );
}

interface SynFixture {
  level:           string;
  integration:     string;
  unification:     string;
  metaConsistency: string;
  metaRisk:        string;
}

function makeSyn({
  level, integration, unification, metaConsistency, metaRisk,
}: SynFixture): string {
  return (
    `=== Structural Governance Synthesis ===\n\n` +
    `[Synthesis Level]\n${level}\n\n` +
    `[Governance Integration]\n${integration}\n\n` +
    `[Governance Unification]\n${unification}\n\n` +
    `[Meta-Consistency]\n${metaConsistency}\n\n` +
    `[Meta-Risk]\n${metaRisk}\n\n` +
    `[Meta-Trajectory]\nlow → low → low (stable)\n\n` +
    `[Synthesis Drivers]\n(none)\n\n` +
    `[Synthesis Inhibitors]\n(none)\n\n` +
    `[Synthesis Risks]\n(none)\n\n` +
    `[Synthesis Reinforcement]\n(none)\n\n` +
    `[Synthesis Decay]\n(none)\n\n` +
    `[System-Level Governance Synthesis Summary]\nStub.`
  );
}

describe("Card 68 — buildSystemLevelGovernance", () => {
  it("baseline LOW → LOW-MEDIUM emits LOW-MEDIUM system governance with all 13 sub-blocks in spec order", () => {
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW-MEDIUM", integrity: "moderate" });
    const res  = makeRes("LOW-MEDIUM");
    const imm  = makeImm({ level: "LOW-MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW-MEDIUM", alignment: "partial", contradiction: "elevated" });
    const syn  = makeSyn({
      level: "LOW-MEDIUM", integration: "partial", unification: "moderate",
      metaConsistency: "partial", metaRisk: "elevated",
    });
    const out  = buildSystemLevelGovernance(gov, diff, stab, res, imm, coh, syn);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== System-Level Governance ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[System Governance Level]")).toBeGreaterThan(idx("=== System-Level Governance ==="));
    expect(idx("[Governance Integrity]")).toBeGreaterThan(idx("[System Governance Level]"));
    expect(idx("[Governance Cohesion]")).toBeGreaterThan(idx("[Governance Integrity]"));
    expect(idx("[Governance Robustness]")).toBeGreaterThan(idx("[Governance Cohesion]"));
    expect(idx("[Governance Meta-Stability]")).toBeGreaterThan(idx("[Governance Robustness]"));
    expect(idx("[Governance Meta-Risk]")).toBeGreaterThan(idx("[Governance Meta-Stability]"));
    expect(idx("[System Governance Trajectory]")).toBeGreaterThan(idx("[Governance Meta-Risk]"));
    expect(idx("[System Governance Drivers]")).toBeGreaterThan(idx("[System Governance Trajectory]"));
    expect(idx("[System Governance Inhibitors]")).toBeGreaterThan(idx("[System Governance Drivers]"));
    expect(idx("[System Governance Risks]")).toBeGreaterThan(idx("[System Governance Inhibitors]"));
    expect(idx("[System Governance Reinforcement]")).toBeGreaterThan(idx("[System Governance Risks]"));
    expect(idx("[System Governance Decay]")).toBeGreaterThan(idx("[System Governance Reinforcement]"));
    expect(idx("[System-Level Governance Summary]")).toBeGreaterThan(idx("[System Governance Decay]"));

    // Derived fields per spec demo.
    expect(out).toContain("[System Governance Level]\nLOW-MEDIUM");
    expect(out).toContain("[Governance Integrity]\npartial");
    expect(out).toContain("[Governance Cohesion]\nmoderate");
    expect(out).toContain("[Governance Robustness]\npartial");
    expect(out).toContain("[Governance Meta-Stability]\nmoderate");
    expect(out).toContain("[Governance Meta-Risk]\nelevated");
    expect(out).toContain("[System Governance Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers (3 lines when slope > 0).
    expect(out).toContain("- improving synthesis");
    expect(out).toContain("- improving coherence");
    expect(out).toContain("- improving immunity trajectory");

    // Inhibitors (3 lines: 2 from Card 61 + 1 profile-derived).
    expect(out).toContain("- CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");

    // Risks (3 lines).
    expect(out).toContain("- cross-layer divergence");
    expect(out).toContain("- threshold misalignment");
    expect(out).toContain("- governance contradiction under pressure");

    // Reinforcement (5 lines — upper-branch=weak drops out, hardening
    // and alignment add the cross-layer reinforcement entries).
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");
    expect(out).toContain("- maintain governance hardening");
    expect(out).toContain("- maintain cross-layer alignment");
    expect(out).not.toContain("- maintain upper-branch containment");

    // Decay (4 lines including coherence-may-degrade for non-strong
    // alignment).
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
    expect(out).toContain("- thresholds may weaken under load");
    expect(out).toContain("- coherence may degrade");
  });

  it("stable system governance MEDIUM → MEDIUM emits MEDIUM + stable trajectory + no drivers/inhibitors", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["moderate", "moderate", "moderate", "moderate"],
    });
    const diff = makeDiff({ direction: "stable", slope: "0", pressure: "low" });
    const stab = makeStab({ level: "MEDIUM", integrity: "moderate" });
    const res  = makeRes("MEDIUM");
    const imm  = makeImm({ level: "MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "MEDIUM", alignment: "partial", contradiction: "low" });
    const syn  = makeSyn({
      level: "MEDIUM", integration: "partial", unification: "strong",
      metaConsistency: "partial", metaRisk: "moderate",
    });
    const out  = buildSystemLevelGovernance(gov, diff, stab, res, imm, coh, syn);

    expect(out).toContain("[System Governance Level]\nMEDIUM");
    expect(out).toContain("[System Governance Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Governance Integrity]\npartial");
    expect(out).toContain("[Governance Cohesion]\nstrong");
    expect(out).toContain("[Governance Robustness]\npartial");
    expect(out).toContain("[Governance Meta-Stability]\nmoderate");
    expect(out).toContain("[System Governance Drivers]\n(none)");
    expect(out).toContain("[System Governance Inhibitors]\n(none)");
    expect(out).toContain("System-level governance is steady with no material changes. Cohesion is strong, and meta-stability is partial.");
  });

  it("deteriorating system governance MEDIUM → LOW-MEDIUM drops the floor with a deteriorating summary", () => {
    const gov = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["partial", "weak", "moderate", "moderate"],
      inhibitors: ["CZ vulnerability", "incomplete drift containment"],
    });
    const diff = makeDiff({ direction: "deteriorating", slope: "-1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW", integrity: "moderate" });
    const res  = makeRes("LOW");
    const imm  = makeImm({ level: "LOW", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW", alignment: "partial", contradiction: "high" });
    const syn  = makeSyn({
      level: "LOW", integration: "weak", unification: "moderate",
      metaConsistency: "weak", metaRisk: "high",
    });
    const out  = buildSystemLevelGovernance(gov, diff, stab, res, imm, coh, syn);

    // min(LOW, LOW, LOW, LOW, LOW)=0 + weak threshold → still 0 → LOW.
    expect(out).toContain("[System Governance Level]\nLOW");
    // contradictionRisk=high → integrity=weak + robustness=weak.
    expect(out).toContain("[Governance Integrity]\nweak");
    expect(out).toContain("[Governance Robustness]\nweak");
    // synthesisMetaRisk=high → meta-risk=high.
    expect(out).toContain("[Governance Meta-Risk]\nhigh");
    expect(out).toContain("[System Governance Trajectory]\nlow-medium → low → low (projected)");
    expect(out).toContain("[System Governance Drivers]\n(none)");
    expect(out).toContain("System-level governance is deteriorating under CZ and drift pressure.");
  });

  it("cross-layer contradiction: stability/resilience HIGH but immunity/coherence/synthesis LOW → cohesion=weak, robustness=weak, meta-risk=high", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "partial"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "low" });
    const stab = makeStab({ level: "MEDIUM-HIGH", integrity: "moderate" });
    const res  = makeRes("MEDIUM-HIGH");
    const imm  = makeImm({ level: "LOW", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW", alignment: "weak", contradiction: "high" });
    const syn  = makeSyn({
      level: "LOW", integration: "weak", unification: "weak",
      metaConsistency: "weak", metaRisk: "high",
    });
    const out  = buildSystemLevelGovernance(gov, diff, stab, res, imm, coh, syn);

    // min(3,3,0,0,0)=0 → system governance floors to LOW.
    expect(out).toContain("[System Governance Level]\nLOW");
    // Spread across all 6 = 3 → cohesion=weak.
    expect(out).toContain("[Governance Cohesion]\nweak");
    // contradictionRisk=high → robustness=weak, integrity=weak.
    expect(out).toContain("[Governance Robustness]\nweak");
    expect(out).toContain("[Governance Integrity]\nweak");
    // integration/unification/metaConsistency all weak → meta-stability=weak.
    expect(out).toContain("[Governance Meta-Stability]\nweak");
    // synthesisMetaRisk=high → meta-risk=high.
    expect(out).toContain("[Governance Meta-Risk]\nhigh");
    // alignment=weak → "maintain cross-layer alignment" drops out.
    expect(out).not.toContain("- maintain cross-layer alignment");
    // alignment != "strong" → "coherence may degrade" still fires.
    expect(out).toContain("- coherence may degrade");
  });

  it("summary correctness: baseline improving + 3 inhibitors mirrors the spec demo phrasing", () => {
    // Spec demo:
    //   "System-level governance is improving but remains vulnerable
    //    to CZ and upper-branch instability. Cohesion is moderate,
    //    and meta-stability is partial."
    // (block "[Meta-Stability] moderate" maps to "partial" in summary.)
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW-MEDIUM", integrity: "moderate" });
    const res  = makeRes("LOW-MEDIUM");
    const imm  = makeImm({ level: "LOW-MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW-MEDIUM", alignment: "partial", contradiction: "elevated" });
    const syn  = makeSyn({
      level: "LOW-MEDIUM", integration: "partial", unification: "moderate",
      metaConsistency: "partial", metaRisk: "elevated",
    });
    const out  = buildSystemLevelGovernance(gov, diff, stab, res, imm, coh, syn);

    expect(out).toContain(
      "System-level governance is improving but remains vulnerable to CZ and upper-branch instability. Cohesion is moderate, and meta-stability is partial.",
    );
  });
});
