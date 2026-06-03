// Card 67 — Structural governance synthesis engine unit tests.
//
// Hand-rolled Card 61 + 62 + 63 + 64 + 65 + 66 text fixtures cover
// the five spec scenarios: baseline synthesis, stable, deteriorating,
// cross-layer contradiction (stability/resilience ≫ immunity), and
// summary correctness.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceSynthesis } from "../operatorStructuralGovernanceSynthesis";

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
  direction:   string;
  slope:       string;
  pressure:    string;
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
  level:      string;
  coherence:  string;
  integrity:  string;
}

function makeStab({ level, coherence, integrity }: StabFixture): string {
  return (
    `=== Structural Governance Stability ===\n\n` +
    `[Stability Level]\n${level}\n\n` +
    `[Governance Coherence]\n${coherence}\n\n` +
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

describe("Card 67 — buildStructuralGovernanceSynthesis", () => {
  it("baseline LOW → LOW-MEDIUM emits LOW-MEDIUM synthesis with all 12 sub-blocks in spec order", () => {
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW-MEDIUM", coherence: "partial", integrity: "moderate" });
    const res  = makeRes("LOW-MEDIUM");
    const imm  = makeImm({ level: "LOW-MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW-MEDIUM", alignment: "partial", contradiction: "elevated" });
    const out  = buildStructuralGovernanceSynthesis(gov, diff, stab, res, imm, coh);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Synthesis ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Synthesis Level]")).toBeGreaterThan(idx("=== Structural Governance Synthesis ==="));
    expect(idx("[Governance Integration]")).toBeGreaterThan(idx("[Synthesis Level]"));
    expect(idx("[Governance Unification]")).toBeGreaterThan(idx("[Governance Integration]"));
    expect(idx("[Meta-Consistency]")).toBeGreaterThan(idx("[Governance Unification]"));
    expect(idx("[Meta-Risk]")).toBeGreaterThan(idx("[Meta-Consistency]"));
    expect(idx("[Meta-Trajectory]")).toBeGreaterThan(idx("[Meta-Risk]"));
    expect(idx("[Synthesis Drivers]")).toBeGreaterThan(idx("[Meta-Trajectory]"));
    expect(idx("[Synthesis Inhibitors]")).toBeGreaterThan(idx("[Synthesis Drivers]"));
    expect(idx("[Synthesis Risks]")).toBeGreaterThan(idx("[Synthesis Inhibitors]"));
    expect(idx("[Synthesis Reinforcement]")).toBeGreaterThan(idx("[Synthesis Risks]"));
    expect(idx("[Synthesis Decay]")).toBeGreaterThan(idx("[Synthesis Reinforcement]"));
    expect(idx("[System-Level Governance Synthesis Summary]")).toBeGreaterThan(idx("[Synthesis Decay]"));

    // Derived fields per spec demo.
    expect(out).toContain("[Synthesis Level]\nLOW-MEDIUM");
    expect(out).toContain("[Governance Integration]\npartial");
    expect(out).toContain("[Governance Unification]\nmoderate");
    expect(out).toContain("[Meta-Consistency]\npartial");
    expect(out).toContain("[Meta-Risk]\nelevated");
    expect(out).toContain("[Meta-Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers (3 lines when slope > 0).
    expect(out).toContain("- improving coherence");
    expect(out).toContain("- improving immunity trajectory");
    expect(out).toContain("- improving resilience");

    // Inhibitors carry over Card 61 wording verbatim.
    expect(out).toContain("- CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");

    // Risks (3 lines: cross-layer divergence + threshold misalignment +
    // governance contradiction).
    expect(out).toContain("- cross-layer divergence");
    expect(out).toContain("- threshold misalignment");
    expect(out).toContain("- governance contradiction under pressure");

    // Reinforcement (5 lines including the new cross-layer alignment).
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");
    expect(out).toContain("- maintain governance hardening");
    expect(out).toContain("- maintain cross-layer alignment");
    // upper-branch=weak in profile → that maintain line drops out.
    expect(out).not.toContain("- maintain upper-branch containment");

    // Decay (4 lines including the new coherence-may-degrade).
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
    expect(out).toContain("- thresholds may weaken under load");
    expect(out).toContain("- coherence may degrade");
  });

  it("stable synthesis MEDIUM → MEDIUM emits MEDIUM synthesis + stable trajectory + no drivers/inhibitors", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["moderate", "moderate", "moderate", "moderate"],
    });
    const diff = makeDiff({ direction: "stable", slope: "0", pressure: "low" });
    const stab = makeStab({ level: "MEDIUM", coherence: "partial", integrity: "moderate" });
    const res  = makeRes("MEDIUM");
    const imm  = makeImm({ level: "MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "MEDIUM", alignment: "partial", contradiction: "low" });
    const out  = buildStructuralGovernanceSynthesis(gov, diff, stab, res, imm, coh);

    expect(out).toContain("[Synthesis Level]\nMEDIUM");
    expect(out).toContain("[Meta-Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Governance Integration]\npartial");
    expect(out).toContain("[Governance Unification]\nstrong");
    expect(out).toContain("[Meta-Risk]\nmoderate");
    expect(out).toContain("[Synthesis Drivers]\n(none)");
    expect(out).toContain("[Synthesis Inhibitors]\n(none)");
    expect(out).toContain("Governance synthesis is steady with no material changes. Integration is partial, and cross-layer alignment is moderate.");
  });

  it("deteriorating synthesis MEDIUM → LOW-MEDIUM drops the floor with a deteriorating summary", () => {
    const gov = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["partial", "weak", "moderate", "moderate"],
      inhibitors: ["CZ vulnerability", "incomplete drift containment"],
    });
    const diff = makeDiff({ direction: "deteriorating", slope: "-1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW", coherence: "partial", integrity: "moderate" });
    const res  = makeRes("LOW");
    const imm  = makeImm({ level: "LOW", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW", alignment: "partial", contradiction: "high" });
    const out  = buildStructuralGovernanceSynthesis(gov, diff, stab, res, imm, coh);

    // min(LOW, LOW, LOW, LOW)=0; threshold=weak triggers a further
    // decrement (clamped at 0) → LOW.
    expect(out).toContain("[Synthesis Level]\nLOW");
    // contradictionRisk=high → meta-consistency=weak, meta-risk=high.
    expect(out).toContain("[Meta-Consistency]\nweak");
    expect(out).toContain("[Meta-Risk]\nhigh");
    expect(out).toContain("[Meta-Trajectory]\nlow-medium → low → low (projected)");
    expect(out).toContain("[Synthesis Drivers]\n(none)");
    expect(out).toContain("Governance synthesis is deteriorating under CZ and drift pressure.");
  });

  it("cross-layer contradiction: stability/resilience HIGH but immunity/coherence LOW → integration=weak, unification=weak, meta-risk=high", () => {
    const gov = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "partial"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "low" });
    const stab = makeStab({ level: "MEDIUM-HIGH", coherence: "partial", integrity: "moderate" });
    const res  = makeRes("MEDIUM-HIGH");
    const imm  = makeImm({ level: "LOW", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW", alignment: "weak", contradiction: "high" });
    const out  = buildStructuralGovernanceSynthesis(gov, diff, stab, res, imm, coh);

    // min(3,3,0,0)=0 → synthesis floors to LOW.
    expect(out).toContain("[Synthesis Level]\nLOW");
    // Spread across upstream layers = 3 → integration=weak.
    expect(out).toContain("[Governance Integration]\nweak");
    // Spread across all 5 = 3 → unification=weak.
    expect(out).toContain("[Governance Unification]\nweak");
    // contradictionRisk=high → meta-consistency=weak, meta-risk=high.
    expect(out).toContain("[Meta-Consistency]\nweak");
    expect(out).toContain("[Meta-Risk]\nhigh");
    // alignment=weak → "maintain cross-layer alignment" drops out of
    // reinforcement; "coherence may degrade" still fires in decay.
    expect(out).not.toContain("- maintain cross-layer alignment");
    expect(out).toContain("- coherence may degrade");
  });

  it("summary correctness: baseline improving + 3 inhibitors mirrors the spec demo phrasing", () => {
    // Spec demo:
    //   "Governance synthesis is improving but remains vulnerable to
    //    CZ and upper-branch instability. Integration is partial,
    //    and cross-layer alignment is moderate."
    // (alignment block is "partial", summary maps to "moderate".)
    const gov = makeGov({
      level:   "LOW",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const diff = makeDiff({ direction: "improving", slope: "+1", pressure: "moderate" });
    const stab = makeStab({ level: "LOW-MEDIUM", coherence: "partial", integrity: "moderate" });
    const res  = makeRes("LOW-MEDIUM");
    const imm  = makeImm({ level: "LOW-MEDIUM", hardening: "partial" });
    const coh  = makeCoh({ level: "LOW-MEDIUM", alignment: "partial", contradiction: "elevated" });
    const out  = buildStructuralGovernanceSynthesis(gov, diff, stab, res, imm, coh);

    expect(out).toContain(
      "Governance synthesis is improving but remains vulnerable to CZ and upper-branch instability. Integration is partial, and cross-layer alignment is moderate.",
    );
  });
});
