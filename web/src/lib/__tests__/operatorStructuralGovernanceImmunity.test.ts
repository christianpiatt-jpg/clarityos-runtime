// Card 65 — Structural governance immunity engine unit tests.
//
// Hand-rolled Card 61 + Card 62 + Card 63 + Card 64 text fixtures
// cover the five spec scenarios: baseline immunity, stable,
// deteriorating, high-vulnerability, and summary correctness. Tests
// pin the parsed-input pipeline against the derived immunity fields
// independently of any future wording tweaks in upstream cards.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceImmunity } from "../operatorStructuralGovernanceImmunity";

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

describe("Card 65 — buildStructuralGovernanceImmunity", () => {
  it("baseline LOW → LOW-MEDIUM emits LOW-MEDIUM immunity with all 13 sub-blocks in spec order", () => {
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
    const res = makeRes("LOW-MEDIUM");
    const out = buildStructuralGovernanceImmunity(gov, diff, stab, res);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Immunity ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Immunity Level]")).toBeGreaterThan(idx("=== Structural Governance Immunity ==="));
    expect(idx("[Future-Resistance]")).toBeGreaterThan(idx("[Immunity Level]"));
    expect(idx("[Governance Hardening]")).toBeGreaterThan(idx("[Future-Resistance]"));
    expect(idx("[Governance Vulnerability]")).toBeGreaterThan(idx("[Governance Hardening]"));
    expect(idx("[Immunity Trajectory]")).toBeGreaterThan(idx("[Governance Vulnerability]"));
    expect(idx("[Immunity Drivers]")).toBeGreaterThan(idx("[Immunity Trajectory]"));
    expect(idx("[Immunity Inhibitors]")).toBeGreaterThan(idx("[Immunity Drivers]"));
    expect(idx("[Immunity Thresholds]")).toBeGreaterThan(idx("[Immunity Inhibitors]"));
    expect(idx("[Immunity Breach Conditions]")).toBeGreaterThan(idx("[Immunity Thresholds]"));
    expect(idx("[Immunity Reinforcement]")).toBeGreaterThan(idx("[Immunity Breach Conditions]"));
    expect(idx("[Immunity Decay]")).toBeGreaterThan(idx("[Immunity Reinforcement]"));
    expect(idx("[Early-Warning Signals]")).toBeGreaterThan(idx("[Immunity Decay]"));
    expect(idx("[System-Level Immunity Summary]")).toBeGreaterThan(idx("[Early-Warning Signals]"));

    // Derived fields per spec demo.
    expect(out).toContain("[Immunity Level]\nLOW-MEDIUM");
    expect(out).toContain("[Future-Resistance]\nmoderate");
    expect(out).toContain("[Governance Hardening]\npartial");
    expect(out).toContain("[Governance Vulnerability]\nelevated");
    expect(out).toContain("[Immunity Trajectory]\nlow → low-medium → medium (projected)");

    // Drivers (3 lines per spec demo).
    expect(out).toContain("- improving governance resilience");
    expect(out).toContain("- reduced governance drift");
    expect(out).toContain("- improved threshold adherence");

    // Inhibitors (3 lines: 2 from Card 62 + 1 profile-derived).
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- partial invariant compliance");

    // Static threshold block always present.
    expect(out).toContain("- CZ < 2");
    expect(out).toContain("- volatility < 2");
    expect(out).toContain("- drift < 1");
    expect(out).toContain("- upper-branch = 0");

    // Breach conditions (3 lines — note "pressure escalation" wording).
    expect(out).toContain("- governance pressure escalation");
    expect(out).toContain("- drift reactivation");
    expect(out).toContain("- threshold breach");

    // Early-warning (3 lines: pressure / inhibitors / weakening stability).
    expect(out).toContain("- rising governance pressure");
    expect(out).toContain("- increasing inhibitors");
    expect(out).toContain("- weakening stability");

    // Reinforcement + decay match Card 64 wording.
    expect(out).toContain("- maintain invariant compliance");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain volatility control");
    expect(out).toContain("- thresholds may weaken under load");
    expect(out).toContain("- drift may re-emerge");
    expect(out).toContain("- volatility may spike");
  });

  it("stable immunity MEDIUM → MEDIUM emits MEDIUM immunity + stable trajectory + empty early-warning", () => {
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
    const out = buildStructuralGovernanceImmunity(gov, diff, stab, res);

    expect(out).toContain("[Immunity Level]\nMEDIUM");
    expect(out).toContain("[Immunity Trajectory]\nmedium → medium → medium (stable)");
    expect(out).toContain("[Future-Resistance]\nmoderate");
    expect(out).toContain("[Governance Vulnerability]\nlow");
    expect(out).toContain("[Immunity Drivers]\n(none)");
    expect(out).toContain("[Immunity Inhibitors]\n(none)");
    // threshold=moderate (rank 1 < 2) still fires "drift reactivation"
    // and "threshold breach" — only a strong threshold clears the
    // breach block entirely.
    expect(out).toContain("- drift reactivation");
    expect(out).toContain("- threshold breach");
    expect(out).not.toContain("- governance pressure escalation");
    expect(out).toContain("[Early-Warning Signals]\n(none)");
    expect(out).toContain("Governance immunity is steady with no material changes. Future-resistance is moderate.");
  });

  it("deteriorating immunity MEDIUM → LOW-MEDIUM clamps resilience further down with a deteriorating summary", () => {
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
    const res = makeRes("LOW");
    const out = buildStructuralGovernanceImmunity(gov, diff, stab, res);

    // resilience=LOW(0) − 1(slope<0) − 1(drift=high) → clamped to 0 → LOW.
    expect(out).toContain("[Immunity Level]\nLOW");
    expect(out).toContain("[Immunity Trajectory]\nlow-medium → low → low (projected)");
    // 4 collected inhibitors (2 delta + partial invariant + weak
    // threshold) → vulnerability=high.
    expect(out).toContain("[Governance Vulnerability]\nhigh");
    expect(out).toContain("Governance immunity is deteriorating under CZ and drift pressure.");
    expect(out).toContain("Future-resistance is moderate, but vulnerabilities persist.");
    // Drivers list empty (slope<0 + no delta drivers).
    expect(out).toContain("[Immunity Drivers]\n(none)");
  });

  it("high-vulnerability scenario: 4+ inhibitors + 3+ weak dims → vulnerability=high, immunity clamped to LOW", () => {
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
    const res = makeRes("LOW");
    const out = buildStructuralGovernanceImmunity(gov, diff, stab, res);

    expect(out).toContain("[Immunity Level]\nLOW");
    expect(out).toContain("[Governance Vulnerability]\nhigh");
    expect(out).toContain("[Future-Resistance]\nweak");
    expect(out).toContain("[Governance Hardening]\nweak");
    // High pressure adds volatility spike + governance pressure escalation
    // to the breach conditions.
    expect(out).toContain("- governance pressure escalation");
    expect(out).toContain("- volatility spike");
    // All 4 early-warning conditions but only 3 actually fire (the
    // 3 collection signals all hit at once).
    expect(out).toContain("- rising governance pressure");
    expect(out).toContain("- increasing inhibitors");
    expect(out).toContain("- weakening stability");
  });

  it("summary correctness: improving + drift improved + persistent vulnerabilities mirrors the spec demo phrasing exactly", () => {
    // Spec demo:
    //   "Governance immunity is improving but remains vulnerable to
    //    CZ and upper-branch instability. Future-resistance is
    //    moderate, but vulnerabilities persist."
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
    const res = makeRes("LOW-MEDIUM");
    const out = buildStructuralGovernanceImmunity(gov, diff, stab, res);

    expect(out).toContain(
      "Governance immunity is improving but remains vulnerable to CZ and upper-branch instability. Future-resistance is moderate, but vulnerabilities persist.",
    );
  });
});
