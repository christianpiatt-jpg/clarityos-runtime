// Card 85 — Operator Meta-Consolidation engine unit tests.
//
// Card 85 consolidates the *levels* of all eight meta-layers — meta-
// pattern (77), meta-stability (78), meta-resilience (79), meta-
// immunity (80), meta-integration (81), meta-alignment (82), meta-
// coherence (83), meta-synthesis (84). The baseline test runs the real
// operator chain end-to-end (so header drift in any upstream card is
// caught); the scenario tests craft minimal upstream strings with
// explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-
// consolidation (+ the capstone VERY-HIGH projected trajectory),
// partial immunity-consolidation, strong synthesis-consolidation, and
// summary correctness.

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
import { buildOperatorMetaConsolidation } from "../operatorMetaConsolidation";

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
function fullChainConsolidation(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  const metaSynthesis = buildOperatorMetaSynthesis(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence,
  );
  return buildOperatorMetaConsolidation(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
  );
}

// Crafted upstream — builds the minimal sections the helper parses,
// with every meta-layer level explicitly set. Defaults are all-optimal.
interface CraftOpts {
  load?: string; drift?: string; clarity?: string; pressure?: string;
  direction?: "improving" | "stable" | "deteriorating";
  metaPattern?: string; metaStability?: string; metaResilience?: string;
  metaImmunity?: string; metaIntegration?: string; metaAlignment?: string;
  metaCoherence?: string; metaSynthesis?: string;
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
  const metaSynthesis   = `=== Operator Meta-Synthesis ===\n\n[Meta-Synthesis Level]\n${o.metaSynthesis ?? "HIGH"}`;

  return buildOperatorMetaConsolidation(
    operatorState, operatorDiff, "", "", "", "", "", "",
    metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
  );
}

describe("Card 85 — buildOperatorMetaConsolidation", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-consolidation + all-strong consolidations + steady summary", () => {
    const out = fullChainConsolidation("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Consolidation ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Consolidation Level]")).toBeGreaterThan(idx("=== Operator Meta-Consolidation ==="));
    expect(idx("[Pattern-Consolidation]")).toBeGreaterThan(idx("[Meta-Consolidation Level]"));
    expect(idx("[Stability-Consolidation]")).toBeGreaterThan(idx("[Pattern-Consolidation]"));
    expect(idx("[Resilience-Consolidation]")).toBeGreaterThan(idx("[Stability-Consolidation]"));
    expect(idx("[Immunity-Consolidation]")).toBeGreaterThan(idx("[Resilience-Consolidation]"));
    expect(idx("[Integration-Consolidation]")).toBeGreaterThan(idx("[Immunity-Consolidation]"));
    expect(idx("[Alignment-Consolidation]")).toBeGreaterThan(idx("[Integration-Consolidation]"));
    expect(idx("[Coherence-Consolidation]")).toBeGreaterThan(idx("[Alignment-Consolidation]"));
    expect(idx("[Synthesis-Consolidation]")).toBeGreaterThan(idx("[Coherence-Consolidation]"));
    expect(idx("[Meta-Consolidation Trajectory]")).toBeGreaterThan(idx("[Synthesis-Consolidation]"));
    expect(idx("[Meta-Consolidation Drivers]")).toBeGreaterThan(idx("[Meta-Consolidation Trajectory]"));
    expect(idx("[Meta-Consolidation Inhibitors]")).toBeGreaterThan(idx("[Meta-Consolidation Drivers]"));
    expect(idx("[Meta-Consolidation Risks]")).toBeGreaterThan(idx("[Meta-Consolidation Inhibitors]"));
    expect(idx("[Meta-Consolidation Reinforcement]")).toBeGreaterThan(idx("[Meta-Consolidation Risks]"));
    expect(idx("[Meta-Consolidation Decay]")).toBeGreaterThan(idx("[Meta-Consolidation Reinforcement]"));
    expect(idx("[Operator Meta-Consolidation Summary]")).toBeGreaterThan(idx("[Meta-Consolidation Decay]"));

    // All-optimal baseline — every consolidated facet reads strong.
    expect(out).toContain("[Meta-Consolidation Level]\nHIGH");
    expect(out).toContain("[Pattern-Consolidation]\nstrong consolidation");
    expect(out).toContain("[Stability-Consolidation]\nstrong consolidation");
    expect(out).toContain("[Resilience-Consolidation]\nstrong consolidation");
    expect(out).toContain("[Immunity-Consolidation]\nstrong consolidation");
    expect(out).toContain("[Integration-Consolidation]\nstrong integration consolidation");
    expect(out).toContain("[Alignment-Consolidation]\nstrong alignment consolidation");
    expect(out).toContain("[Coherence-Consolidation]\nstrong coherence consolidation");
    expect(out).toContain("[Synthesis-Consolidation]\nstrong synthesis consolidation");
    expect(out).toContain("[Meta-Consolidation Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong pattern consolidation");
    expect(out).toContain("- strong resilience consolidation");
    expect(out).toContain("- strong synthesis consolidation");
    expect(out).toContain("[Meta-Consolidation Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Consolidation Risks]\n(none)");
    expect(out).toContain("[Meta-Consolidation Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-consolidation is steady, with strong pattern-, resilience-, and synthesis-consolidation.",
    );
    expect(out).not.toContain("Immunity-consolidation remains");
  });

  it("strong pattern-consolidation scenario: all MEDIUM-HIGH + improving → 'strong consolidation', driver, and the VERY-HIGH projection", () => {
    const out = craft({
      direction:       "improving",
      metaPattern:     "MEDIUM-HIGH",
      metaStability:   "MEDIUM-HIGH",
      metaResilience:  "MEDIUM-HIGH",
      metaImmunity:    "MEDIUM-HIGH",
      metaIntegration: "MEDIUM-HIGH",
      metaAlignment:   "MEDIUM-HIGH",
      metaCoherence:   "MEDIUM-HIGH",
      metaSynthesis:   "MEDIUM-HIGH",
    });

    expect(out).toContain("[Pattern-Consolidation]\nstrong consolidation");
    expect(out).toContain("- strong pattern consolidation");
    // Forward projection from a MEDIUM-HIGH level reaches the VERY-HIGH band.
    expect(out).toContain("[Meta-Consolidation Trajectory]\nmedium-high → high → very-high (projected)");
  });

  it("partial immunity-consolidation scenario: meta-immunity level LOW-MEDIUM → 'partial consolidation' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Consolidation]\npartial consolidation");
    expect(out).toContain("- partial immunity consolidation");
    expect(out).toContain("- strengthen immunity consolidation");
  });

  it("strong synthesis-consolidation scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis consolidation' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Consolidation]\nstrong synthesis consolidation");
    expect(out).toContain("- strong synthesis consolidation");
  });

  it("summary correctness: improving + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-consolidation is strengthening, with strong
    //    pattern-, resilience-, and synthesis-consolidation. Immunity-
    //    consolidation remains partial and may disrupt overall
    //    consolidation."
    const out = craft({
      direction:      "improving",
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-consolidation is strengthening, with strong pattern-, resilience-, and synthesis-consolidation. Immunity-consolidation remains partial and may disrupt overall consolidation.",
    );
  });
});
