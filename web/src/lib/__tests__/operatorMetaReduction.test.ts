// Card 87 — Operator Meta-Reduction engine unit tests.
//
// Card 87 reduces the *levels* of all ten meta-layers — meta-pattern
// (77) … meta-compression (86). The baseline test runs the real
// operator chain end-to-end (so header drift in any upstream card is
// caught); the scenario tests craft minimal upstream strings with
// explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-
// reduction (+ the VERY-HIGH projected trajectory), partial immunity-
// reduction, strong synthesis-reduction, and summary correctness.

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
import { buildOperatorMetaCompression }  from "../operatorMetaCompression";
import { buildOperatorMetaReduction }    from "../operatorMetaReduction";

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
function fullChainReduction(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  const metaConsolidation = buildOperatorMetaConsolidation(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
  );
  const metaCompression = buildOperatorMetaCompression(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis, metaConsolidation,
  );
  return buildOperatorMetaReduction(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis, metaConsolidation, metaCompression,
  );
}

// Crafted upstream — builds the minimal sections the helper parses,
// with every meta-layer level explicitly set. Defaults are all-optimal.
interface CraftOpts {
  load?: string; drift?: string; clarity?: string; pressure?: string;
  direction?: "improving" | "stable" | "deteriorating";
  metaPattern?: string; metaStability?: string; metaResilience?: string;
  metaImmunity?: string; metaIntegration?: string; metaAlignment?: string;
  metaCoherence?: string; metaSynthesis?: string; metaConsolidation?: string;
  metaCompression?: string;
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

  const mp = `=== Operator Meta-Pattern ===\n\n[Meta-Pattern Level]\n${o.metaPattern ?? "HIGH"}`;
  const ms = `=== Operator Meta-Stability ===\n\n[Meta-Stability Level]\n${o.metaStability ?? "HIGH"}`;
  const mr = `=== Operator Meta-Resilience ===\n\n[Meta-Resilience Level]\n${o.metaResilience ?? "HIGH"}`;
  const mi = `=== Operator Meta-Immunity ===\n\n[Meta-Immunity Level]\n${o.metaImmunity ?? "HIGH"}`;
  const mn = `=== Operator Meta-Integration ===\n\n[Meta-Integration Level]\n${o.metaIntegration ?? "HIGH"}`;
  const ma = `=== Operator Meta-Alignment ===\n\n[Meta-Alignment Level]\n${o.metaAlignment ?? "HIGH"}`;
  const mc = `=== Operator Meta-Coherence ===\n\n[Meta-Coherence Level]\n${o.metaCoherence ?? "HIGH"}`;
  const my = `=== Operator Meta-Synthesis ===\n\n[Meta-Synthesis Level]\n${o.metaSynthesis ?? "HIGH"}`;
  const mo = `=== Operator Meta-Consolidation ===\n\n[Meta-Consolidation Level]\n${o.metaConsolidation ?? "HIGH"}`;
  const mz = `=== Operator Meta-Compression ===\n\n[Meta-Compression Level]\n${o.metaCompression ?? "HIGH"}`;

  return buildOperatorMetaReduction(
    operatorState, operatorDiff, "", "", "", "", "", "",
    mp, ms, mr, mi, mn, ma, mc, my, mo, mz,
  );
}

describe("Card 87 — buildOperatorMetaReduction", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-reduction + all-strong reductions + steady summary", () => {
    const out = fullChainReduction("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Reduction ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Reduction Level]")).toBeGreaterThan(idx("=== Operator Meta-Reduction ==="));
    expect(idx("[Pattern-Reduction]")).toBeGreaterThan(idx("[Meta-Reduction Level]"));
    expect(idx("[Stability-Reduction]")).toBeGreaterThan(idx("[Pattern-Reduction]"));
    expect(idx("[Resilience-Reduction]")).toBeGreaterThan(idx("[Stability-Reduction]"));
    expect(idx("[Immunity-Reduction]")).toBeGreaterThan(idx("[Resilience-Reduction]"));
    expect(idx("[Integration-Reduction]")).toBeGreaterThan(idx("[Immunity-Reduction]"));
    expect(idx("[Alignment-Reduction]")).toBeGreaterThan(idx("[Integration-Reduction]"));
    expect(idx("[Coherence-Reduction]")).toBeGreaterThan(idx("[Alignment-Reduction]"));
    expect(idx("[Synthesis-Reduction]")).toBeGreaterThan(idx("[Coherence-Reduction]"));
    expect(idx("[Consolidation-Reduction]")).toBeGreaterThan(idx("[Synthesis-Reduction]"));
    expect(idx("[Compression-Reduction]")).toBeGreaterThan(idx("[Consolidation-Reduction]"));
    expect(idx("[Meta-Reduction Trajectory]")).toBeGreaterThan(idx("[Compression-Reduction]"));
    expect(idx("[Meta-Reduction Drivers]")).toBeGreaterThan(idx("[Meta-Reduction Trajectory]"));
    expect(idx("[Meta-Reduction Inhibitors]")).toBeGreaterThan(idx("[Meta-Reduction Drivers]"));
    expect(idx("[Meta-Reduction Risks]")).toBeGreaterThan(idx("[Meta-Reduction Inhibitors]"));
    expect(idx("[Meta-Reduction Reinforcement]")).toBeGreaterThan(idx("[Meta-Reduction Risks]"));
    expect(idx("[Meta-Reduction Decay]")).toBeGreaterThan(idx("[Meta-Reduction Reinforcement]"));
    expect(idx("[Operator Meta-Reduction Summary]")).toBeGreaterThan(idx("[Meta-Reduction Decay]"));

    // All-optimal baseline — every reduced facet reads strong.
    expect(out).toContain("[Meta-Reduction Level]\nHIGH");
    expect(out).toContain("[Pattern-Reduction]\nstrong reduction");
    expect(out).toContain("[Stability-Reduction]\nstrong reduction");
    expect(out).toContain("[Resilience-Reduction]\nstrong reduction");
    expect(out).toContain("[Immunity-Reduction]\nstrong reduction");
    expect(out).toContain("[Integration-Reduction]\nstrong integration reduction");
    expect(out).toContain("[Alignment-Reduction]\nstrong alignment reduction");
    expect(out).toContain("[Coherence-Reduction]\nstrong coherence reduction");
    expect(out).toContain("[Synthesis-Reduction]\nstrong synthesis reduction");
    expect(out).toContain("[Consolidation-Reduction]\nstrong consolidation reduction");
    expect(out).toContain("[Compression-Reduction]\nstrong compression reduction");
    expect(out).toContain("[Meta-Reduction Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong pattern reduction");
    expect(out).toContain("- strong resilience reduction");
    expect(out).toContain("- strong synthesis reduction");
    expect(out).toContain("[Meta-Reduction Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Reduction Risks]\n(none)");
    expect(out).toContain("[Meta-Reduction Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-reduction is steady, with strong pattern-, resilience-, and synthesis-reduction.",
    );
    expect(out).not.toContain("Immunity-reduction remains");
  });

  it("strong pattern-reduction scenario: all MEDIUM-HIGH + improving → 'strong reduction', driver, and the VERY-HIGH projection", () => {
    const out = craft({
      direction:         "improving",
      metaPattern:       "MEDIUM-HIGH",
      metaStability:     "MEDIUM-HIGH",
      metaResilience:    "MEDIUM-HIGH",
      metaImmunity:      "MEDIUM-HIGH",
      metaIntegration:   "MEDIUM-HIGH",
      metaAlignment:     "MEDIUM-HIGH",
      metaCoherence:     "MEDIUM-HIGH",
      metaSynthesis:     "MEDIUM-HIGH",
      metaConsolidation: "MEDIUM-HIGH",
      metaCompression:   "MEDIUM-HIGH",
    });

    expect(out).toContain("[Pattern-Reduction]\nstrong reduction");
    expect(out).toContain("- strong pattern reduction");
    // Forward projection from a MEDIUM-HIGH level reaches the VERY-HIGH band.
    expect(out).toContain("[Meta-Reduction Trajectory]\nmedium-high → high → very-high (projected)");
  });

  it("partial immunity-reduction scenario: meta-immunity level LOW-MEDIUM → 'partial reduction' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Reduction]\npartial reduction");
    expect(out).toContain("- partial immunity reduction");
    expect(out).toContain("- strengthen immunity reduction");
  });

  it("strong synthesis-reduction scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis reduction' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Reduction]\nstrong synthesis reduction");
    expect(out).toContain("- strong synthesis reduction");
  });

  it("summary correctness: improving + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-reduction is strengthening, with strong pattern-,
    //    resilience-, and synthesis-reduction. Immunity-reduction
    //    remains partial and may disrupt overall reduction."
    const out = craft({
      direction:      "improving",
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-reduction is strengthening, with strong pattern-, resilience-, and synthesis-reduction. Immunity-reduction remains partial and may disrupt overall reduction.",
    );
  });
});
