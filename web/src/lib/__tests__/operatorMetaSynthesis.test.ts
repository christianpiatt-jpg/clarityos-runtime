// Card 84 — Operator Meta-Synthesis engine unit tests.
//
// Card 84 unifies the *levels* of the seven meta-layers — meta-pattern
// (77), meta-stability (78), meta-resilience (79), meta-immunity (80),
// meta-integration (81), meta-alignment (82), meta-coherence (83). The
// baseline test runs the real operator chain end-to-end (so header
// drift in any upstream card is caught); the scenario tests craft
// minimal upstream strings with explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong coherence-
// synthesis (+ the capstone VERY-HIGH projected trajectory), partial
// immunity-synthesis, strong integration-synthesis, and summary
// correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }            from "../operatorState";
import { buildOperatorDiff }             from "../operatorStateDiff";
import { buildOperatorStability }        from "../operatorStability";
import { buildOperatorResilience }       from "../operatorResilience";
import { buildOperatorImmunity }         from "../operatorImmunity";
import { buildOperatorCoherence }        from "../operatorCoherence";
import { buildOperatorSynthesis }        from "../operatorSynthesis";
import { buildSystemOperatorIntegration } from "../systemOperatorIntegration";
import { buildOperatorMetaPattern }      from "../operatorMetaPattern";
import { buildOperatorMetaStability }    from "../operatorMetaStability";
import { buildOperatorMetaResilience }   from "../operatorMetaResilience";
import { buildOperatorMetaImmunity }     from "../operatorMetaImmunity";
import { buildOperatorMetaIntegration }  from "../operatorMetaIntegration";
import { buildOperatorMetaAlignment }    from "../operatorMetaAlignment";
import { buildOperatorMetaCoherence }    from "../operatorMetaCoherence";
import { buildOperatorMetaSynthesis }    from "../operatorMetaSynthesis";

function sysImmunity(score: string): string {
  return `=== Structural Immunity ===\n\n[Immunity Score]\n${score}\n`;
}
function sysResilience(score: string): string {
  return `=== Structural Resilience ===\n\n[Resilience Score]\n${score}\n`;
}
function sysStability(prob: string): string {
  return `=== Structural Stabilization ===\n\n[Stabilization Probability]\n${prob}\n`;
}

// Real end-to-end chain — used for the baseline test so the helper is
// exercised against the actual section headers each upstream card emits.
function fullChainSynthesis(prevInput: string, currInput: string, systemScore = "HIGH"): string {
  const prevState  = buildOperatorState(prevInput);
  const currState  = buildOperatorState(currInput);
  const diff       = buildOperatorDiff(prevState, currState);
  const stability  = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  const immunity   = buildOperatorImmunity(currState, diff, stability, resilience);
  const coherence  = buildOperatorCoherence(currState, diff, stability, resilience, immunity);
  const synthesis  = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);
  const integration = buildSystemOperatorIntegration(
    "", "",
    sysStability(systemScore), sysResilience(systemScore), sysImmunity(systemScore),
    currState, diff, stability, resilience, immunity, coherence, synthesis,
  );
  const metaPattern = buildOperatorMetaPattern(
    currState, diff, stability, resilience, immunity, coherence, synthesis, integration,
  );
  const metaStability = buildOperatorMetaStability(
    currState, diff, stability, resilience, immunity, coherence, synthesis, integration, metaPattern,
  );
  const metaResilience = buildOperatorMetaResilience(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability,
  );
  const metaImmunity = buildOperatorMetaImmunity(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience,
  );
  const metaIntegration = buildOperatorMetaIntegration(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
  );
  const metaAlignment = buildOperatorMetaAlignment(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity, metaIntegration,
  );
  const metaCoherence = buildOperatorMetaCoherence(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity, metaIntegration, metaAlignment,
  );
  return buildOperatorMetaSynthesis(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence,
  );
}

// Crafted upstream — builds the minimal sections the helper parses,
// with every meta-layer level explicitly set. Defaults are all-optimal.
interface CraftOpts {
  load?: string; drift?: string; clarity?: string; pressure?: string;
  direction?: "improving" | "stable" | "deteriorating";
  metaPattern?: string; metaStability?: string; metaResilience?: string;
  metaImmunity?: string; metaIntegration?: string; metaAlignment?: string;
  metaCoherence?: string;
}

function craft(o: CraftOpts = {}): string {
  const load     = o.load ?? "low";
  const drift    = o.drift ?? "low";
  const clarity  = o.clarity ?? "strong";
  const pressure = o.pressure ?? "low";
  const direction = o.direction ?? "stable";

  const operatorState = [
    "=== Operator State ===",
    `[Operator Load]\n${load}`,
    `[Operator Drift]\n${drift}`,
    `[Operator Clarity]\n${clarity}`,
    `[Operator Pressure]\n${pressure}`,
  ].join("\n\n");

  const dsum =
    direction === "improving"     ? "Operator trajectory is improving." :
    direction === "deteriorating" ? "Operator trajectory is deteriorating." :
    "Operator trajectory is steady.";
  const operatorDiff = `=== Operator Diff ===\n\n[Operator Diff Summary]\n${dsum}`;

  const metaPattern     = `=== Operator Meta-Pattern ===\n\n[Meta-Pattern Level]\n${o.metaPattern ?? "HIGH"}`;
  const metaStability   = `=== Operator Meta-Stability ===\n\n[Meta-Stability Level]\n${o.metaStability ?? "HIGH"}`;
  const metaResilience  = `=== Operator Meta-Resilience ===\n\n[Meta-Resilience Level]\n${o.metaResilience ?? "HIGH"}`;
  const metaImmunity    = `=== Operator Meta-Immunity ===\n\n[Meta-Immunity Level]\n${o.metaImmunity ?? "HIGH"}`;
  const metaIntegration = `=== Operator Meta-Integration ===\n\n[Meta-Integration Level]\n${o.metaIntegration ?? "HIGH"}`;
  const metaAlignment   = `=== Operator Meta-Alignment ===\n\n[Meta-Alignment Level]\n${o.metaAlignment ?? "HIGH"}`;
  const metaCoherence   = `=== Operator Meta-Coherence ===\n\n[Meta-Coherence Level]\n${o.metaCoherence ?? "HIGH"}`;

  return buildOperatorMetaSynthesis(
    operatorState, operatorDiff, "", "", "", "", "", "",
    metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence,
  );
}

describe("Card 84 — buildOperatorMetaSynthesis", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-synthesis + all-strong syntheses + capstone summary", () => {
    const out = fullChainSynthesis("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Synthesis ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Synthesis Level]")).toBeGreaterThan(idx("=== Operator Meta-Synthesis ==="));
    expect(idx("[Coherence-Synthesis]")).toBeGreaterThan(idx("[Meta-Synthesis Level]"));
    expect(idx("[Stability-Synthesis]")).toBeGreaterThan(idx("[Coherence-Synthesis]"));
    expect(idx("[Resilience-Synthesis]")).toBeGreaterThan(idx("[Stability-Synthesis]"));
    expect(idx("[Immunity-Synthesis]")).toBeGreaterThan(idx("[Resilience-Synthesis]"));
    expect(idx("[Integration-Synthesis]")).toBeGreaterThan(idx("[Immunity-Synthesis]"));
    expect(idx("[Alignment-Synthesis]")).toBeGreaterThan(idx("[Integration-Synthesis]"));
    expect(idx("[Pattern-Synthesis]")).toBeGreaterThan(idx("[Alignment-Synthesis]"));
    expect(idx("[Meta-Synthesis Trajectory]")).toBeGreaterThan(idx("[Pattern-Synthesis]"));
    expect(idx("[Meta-Synthesis Drivers]")).toBeGreaterThan(idx("[Meta-Synthesis Trajectory]"));
    expect(idx("[Meta-Synthesis Inhibitors]")).toBeGreaterThan(idx("[Meta-Synthesis Drivers]"));
    expect(idx("[Meta-Synthesis Risks]")).toBeGreaterThan(idx("[Meta-Synthesis Inhibitors]"));
    expect(idx("[Meta-Synthesis Reinforcement]")).toBeGreaterThan(idx("[Meta-Synthesis Risks]"));
    expect(idx("[Meta-Synthesis Decay]")).toBeGreaterThan(idx("[Meta-Synthesis Reinforcement]"));
    expect(idx("[Operator Meta-Synthesis Summary]")).toBeGreaterThan(idx("[Meta-Synthesis Decay]"));

    // All-optimal baseline — every unified facet reads strong.
    expect(out).toContain("[Meta-Synthesis Level]\nHIGH");
    expect(out).toContain("[Coherence-Synthesis]\nstrong synthesis");
    expect(out).toContain("[Stability-Synthesis]\nstrong synthesis");
    expect(out).toContain("[Resilience-Synthesis]\nstrong synthesis");
    expect(out).toContain("[Immunity-Synthesis]\nstrong synthesis");
    expect(out).toContain("[Integration-Synthesis]\nstrong integration synthesis");
    expect(out).toContain("[Alignment-Synthesis]\nstrong alignment synthesis");
    expect(out).toContain("[Pattern-Synthesis]\nstable pattern synthesis");
    // Baseline is stable → trajectory holds at HIGH (no VERY-HIGH projection).
    expect(out).toContain("[Meta-Synthesis Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong coherence synthesis");
    expect(out).toContain("- strong resilience synthesis");
    expect(out).toContain("- strong integration synthesis");
    expect(out).toContain("[Meta-Synthesis Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Synthesis Risks]\n(none)");
    expect(out).toContain("[Meta-Synthesis Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-synthesis is strong, with high coherence-, resilience-, and integration-synthesis.",
    );
    expect(out).not.toContain("Immunity-synthesis remains");
  });

  it("strong coherence-synthesis scenario: all-HIGH + improving → 'strong synthesis', driver, and the capstone VERY-HIGH projection", () => {
    const out = craft({ direction: "improving" });

    expect(out).toContain("[Coherence-Synthesis]\nstrong synthesis");
    expect(out).toContain("- strong coherence synthesis");
    // Capstone: improving from a HIGH level projects into the VERY-HIGH band.
    expect(out).toContain("[Meta-Synthesis Trajectory]\nmedium-high → high → very-high (projected)");
  });

  it("partial immunity-synthesis scenario: meta-immunity level LOW-MEDIUM → 'partial synthesis' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Synthesis]\npartial synthesis");
    expect(out).toContain("- partial immunity synthesis");
    expect(out).toContain("- strengthen immunity synthesis");
  });

  it("strong integration-synthesis scenario: meta-integration level MEDIUM-HIGH → 'strong integration synthesis' + driver", () => {
    const out = craft({ metaIntegration: "MEDIUM-HIGH" });

    expect(out).toContain("[Integration-Synthesis]\nstrong integration synthesis");
    expect(out).toContain("- strong integration synthesis");
  });

  it("summary correctness: strong + high coherence/resilience/integration + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-synthesis is strong, with high coherence-,
    //    resilience-, and integration-synthesis. Immunity-synthesis
    //    remains partial and may disrupt overall synthesis."
    const out = craft({
      direction:       "improving",
      metaCoherence:   "HIGH",
      metaResilience:  "HIGH",
      metaIntegration: "HIGH",
      metaImmunity:    "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-synthesis is strong, with high coherence-, resilience-, and integration-synthesis. Immunity-synthesis remains partial and may disrupt overall synthesis.",
    );
  });
});
