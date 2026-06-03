// Card 62 — Structural governance diff engine unit tests.
//
// Hand-rolled Card 61-shape governance text fixtures cover the five
// spec scenarios: baseline improvement, stable, deterioration, high-
// pressure, and summary correctness. Tests pin the parsed-delta logic
// without depending on the Card 61 helper output verbatim, so the
// suite stays decoupled from any future Card 61 wording tweaks.

import { describe, expect, it } from "vitest";

import { buildStructuralGovernanceDiff } from "../operatorStructuralGovernanceDiff";

interface GovernanceFixture {
  level:        string;
  profile:      [string, string, string, string]; // 4 profile words in spec order
  inhibitors?:  string[];
}

// Build a minimal Card 61-shape governance text block. Only the
// sections the diff helper actually parses (Level, Profile,
// Inhibitors) are populated; the rest are stubbed so the parser
// doesn't accidentally pull from neighbouring sections.
function makeGov({ level, profile, inhibitors = [] }: GovernanceFixture): string {
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

describe("Card 62 — buildStructuralGovernanceDiff", () => {
  it("baseline improvement LOW → LOW-MEDIUM emits +1 slope and improving direction with driver lines", () => {
    const prev = makeGov({
      level:   "LOW",
      profile: ["weak", "weak", "weak", "weak"],
      inhibitors: [
        "CZ vulnerability",
        "incomplete drift containment",
        "volatility breach",
      ],
    });
    const next = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["partial", "moderate", "weak", "moderate"],
      inhibitors: [
        "CZ vulnerability",
        "upper-branch instability",
      ],
    });
    const out = buildStructuralGovernanceDiff(prev, next);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance Diff ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Governance Delta]")).toBeGreaterThan(idx("=== Structural Governance Diff ==="));
    expect(idx("[Governance Direction]")).toBeGreaterThan(idx("[Governance Delta]"));
    expect(idx("[Governance Slope]")).toBeGreaterThan(idx("[Governance Direction]"));
    expect(idx("[Governance Pressure]")).toBeGreaterThan(idx("[Governance Slope]"));
    expect(idx("[Governance Stability]")).toBeGreaterThan(idx("[Governance Pressure]"));
    expect(idx("[Governance Risk]")).toBeGreaterThan(idx("[Governance Stability]"));
    expect(idx("[Governance Delta Drivers]")).toBeGreaterThan(idx("[Governance Risk]"));
    expect(idx("[Governance Delta Inhibitors]")).toBeGreaterThan(idx("[Governance Delta Drivers]"));
    expect(idx("[Governance Delta Summary]")).toBeGreaterThan(idx("[Governance Delta Inhibitors]"));

    // Delta + direction + slope.
    expect(out).toContain("[Governance Delta]\nLOW → LOW-MEDIUM");
    expect(out).toContain("[Governance Direction]\nimproving");
    expect(out).toContain("[Governance Slope]\n+1");
    // Two next-inhibitors → moderate pressure.
    expect(out).toContain("[Governance Pressure]\nmoderate");
    // Mixed profile (1 weak, 3 partial/moderate) → partial stability.
    expect(out).toContain("[Governance Stability]\npartial");
    // Moderate pressure + non-negative slope → elevated risk.
    expect(out).toContain("[Governance Risk]\nelevated");

    // Driver list orders by mild-first: volatility, threshold(=drift),
    // invariant. All three improved (weak → moderate/partial).
    expect(out).toContain("- improved volatility control");
    expect(out).toContain("- improved drift suppression");
    expect(out).toContain("- improved invariant compliance");
    // Upper-branch profile stayed weak → no upper-branch driver.
    expect(out).not.toContain("- improved upper-branch containment");

    // Inhibitor list: CZ was in prev too → persistent. upper-branch
    // was not → no prefix.
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
  });

  it("stable governance MEDIUM → MEDIUM emits 0 slope and the no-change summary", () => {
    const prev = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "moderate"],
    });
    const next = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "moderate"],
    });
    const out = buildStructuralGovernanceDiff(prev, next);

    expect(out).toContain("[Governance Delta]\nMEDIUM → MEDIUM");
    expect(out).toContain("[Governance Direction]\nstable");
    expect(out).toContain("[Governance Slope]\n0");
    expect(out).toContain("[Governance Pressure]\nlow");
    expect(out).toContain("[Governance Stability]\npartial");
    expect(out).toContain("[Governance Risk]\nlow");
    expect(out).toContain("[Governance Delta Drivers]\n(none)");
    expect(out).toContain("[Governance Delta Inhibitors]\n(none)");
    expect(out).toContain("Governance remains stable with no material change.");
  });

  it("deterioration MEDIUM → LOW-MEDIUM emits -1 slope and worsening inhibitor lines", () => {
    const prev = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "moderate"],
    });
    const next = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["weak", "weak", "moderate", "moderate"],
      inhibitors: ["CZ vulnerability", "incomplete drift containment"],
    });
    const out = buildStructuralGovernanceDiff(prev, next);

    expect(out).toContain("[Governance Delta]\nMEDIUM → LOW-MEDIUM");
    expect(out).toContain("[Governance Direction]\ndeteriorating");
    expect(out).toContain("[Governance Slope]\n-1");
    expect(out).toContain("[Governance Pressure]\nmoderate");
    // Moderate pressure + negative slope → high risk per riskOf rule.
    expect(out).toContain("[Governance Risk]\nhigh");

    // Two profile dims regressed (invariant + threshold) → weakening
    // inhibitor lines surface alongside next.inhibitors.
    expect(out).toContain("- weakening invariant compliance");
    expect(out).toContain("- weakening drift suppression");
    expect(out).toContain("- CZ vulnerability");

    // Drivers list is empty (no dim improved).
    expect(out).toContain("[Governance Delta Drivers]\n(none)");
    // Deteriorating summary clause mentions vulnerabilities expanding.
    expect(out).toContain("vulnerabilities expand.");
  });

  it("high-pressure scenario: 3+ next inhibitors → pressure=high and risk=high", () => {
    const prev = makeGov({
      level:   "MEDIUM",
      profile: ["partial", "moderate", "moderate", "moderate"],
    });
    const next = makeGov({
      level:   "LOW",
      profile: ["weak", "weak", "weak", "weak"],
      inhibitors: [
        "CZ vulnerability",
        "upper-branch instability",
        "incomplete drift containment",
        "volatility breach",
      ],
    });
    const out = buildStructuralGovernanceDiff(prev, next);

    expect(out).toContain("[Governance Pressure]\nhigh");
    expect(out).toContain("[Governance Risk]\nhigh");
    expect(out).toContain("[Governance Stability]\nweak");
    expect(out).toContain("[Governance Direction]\ndeteriorating");
  });

  it("summary correctness: improving with drivers + persistent inhibitors mirrors the spec demo phrasing", () => {
    // Spec demo: prev had CZ vulnerability + volatility breach +
    // weak drift control. Next: CZ persistent + upper-branch new,
    // volatility + drift improved. Expected summary phrasing:
    //   "Governance shows a modest improvement driven by volatility
    //    and drift stabilization, but CZ and upper-branch
    //    vulnerabilities continue to limit overall stability."
    const prev = makeGov({
      level:   "LOW",
      profile: ["partial", "weak", "strong", "weak"],
      inhibitors: ["CZ vulnerability", "volatility breach"],
    });
    const next = makeGov({
      level:   "LOW-MEDIUM",
      profile: ["partial", "moderate", "strong", "moderate"],
      inhibitors: ["CZ vulnerability", "upper-branch instability"],
    });
    const out = buildStructuralGovernanceDiff(prev, next);

    expect(out).toContain(
      "Governance shows a modest improvement driven by volatility and drift stabilization, but CZ and upper-branch vulnerabilities continue to limit overall stability.",
    );
    // And the structured drivers/inhibitors lists match.
    expect(out).toContain("- improved volatility control");
    expect(out).toContain("- improved drift suppression");
    expect(out).toContain("- persistent CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
  });
});
