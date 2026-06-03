// Card 89 — Operator Meta-Distillation engine unit tests.
//
// Card 89 distills the essential signal from the *levels* of all twelve
// meta-layers — meta-pattern (77) … meta-extraction (88). The baseline
// test runs the real operator chain end-to-end (so header drift in any
// upstream card is caught); the scenario tests craft minimal upstream
// strings with explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-
// distillation (+ the capstone PEAK projected trajectory), partial
// immunity-distillation, strong synthesis-distillation, and summary
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
import { buildOperatorMetaConsolidation } from "../operatorMetaConsolidation";
import { buildOperatorMetaCompression }  from "../operatorMetaCompression";
import { buildOperatorMetaReduction }    from "../operatorMetaReduction";
import { buildOperatorMetaExtraction }   from "../operatorMetaExtraction";
import { buildOperatorMetaDistillation } from "../operatorMetaDistillation";

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
function fullChainDistillation(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  const metaReduction = buildOperatorMetaReduction(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis, metaConsolidation, metaCompression,
  );
  const metaExtraction = buildOperatorMetaExtraction(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction,
  );
  return buildOperatorMetaDistillation(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction, metaExtraction,
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
  metaCompression?: string; metaReduction?: string; metaExtraction?: string;
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
  const md = `=== Operator Meta-Reduction ===\n\n[Meta-Reduction Level]\n${o.metaReduction ?? "HIGH"}`;
  const me = `=== Operator Meta-Extraction ===\n\n[Meta-Extraction Level]\n${o.metaExtraction ?? "HIGH"}`;

  return buildOperatorMetaDistillation(
    operatorState, operatorDiff, "", "", "", "", "", "",
    mp, ms, mr, mi, mn, ma, mc, my, mo, mz, md, me,
  );
}

describe("Card 89 — buildOperatorMetaDistillation", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-distillation + all-strong distillations + capstone summary", () => {
    const out = fullChainDistillation("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Distillation ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Distillation Level]")).toBeGreaterThan(idx("=== Operator Meta-Distillation ==="));
    expect(idx("[Pattern-Distillation]")).toBeGreaterThan(idx("[Meta-Distillation Level]"));
    expect(idx("[Stability-Distillation]")).toBeGreaterThan(idx("[Pattern-Distillation]"));
    expect(idx("[Resilience-Distillation]")).toBeGreaterThan(idx("[Stability-Distillation]"));
    expect(idx("[Immunity-Distillation]")).toBeGreaterThan(idx("[Resilience-Distillation]"));
    expect(idx("[Integration-Distillation]")).toBeGreaterThan(idx("[Immunity-Distillation]"));
    expect(idx("[Alignment-Distillation]")).toBeGreaterThan(idx("[Integration-Distillation]"));
    expect(idx("[Coherence-Distillation]")).toBeGreaterThan(idx("[Alignment-Distillation]"));
    expect(idx("[Synthesis-Distillation]")).toBeGreaterThan(idx("[Coherence-Distillation]"));
    expect(idx("[Consolidation-Distillation]")).toBeGreaterThan(idx("[Synthesis-Distillation]"));
    expect(idx("[Compression-Distillation]")).toBeGreaterThan(idx("[Consolidation-Distillation]"));
    expect(idx("[Reduction-Distillation]")).toBeGreaterThan(idx("[Compression-Distillation]"));
    expect(idx("[Extraction-Distillation]")).toBeGreaterThan(idx("[Reduction-Distillation]"));
    expect(idx("[Meta-Distillation Trajectory]")).toBeGreaterThan(idx("[Extraction-Distillation]"));
    expect(idx("[Meta-Distillation Drivers]")).toBeGreaterThan(idx("[Meta-Distillation Trajectory]"));
    expect(idx("[Meta-Distillation Inhibitors]")).toBeGreaterThan(idx("[Meta-Distillation Drivers]"));
    expect(idx("[Meta-Distillation Risks]")).toBeGreaterThan(idx("[Meta-Distillation Inhibitors]"));
    expect(idx("[Meta-Distillation Reinforcement]")).toBeGreaterThan(idx("[Meta-Distillation Risks]"));
    expect(idx("[Meta-Distillation Decay]")).toBeGreaterThan(idx("[Meta-Distillation Reinforcement]"));
    expect(idx("[Operator Meta-Distillation Summary]")).toBeGreaterThan(idx("[Meta-Distillation Decay]"));

    // All-optimal baseline — every distilled facet reads strong.
    expect(out).toContain("[Meta-Distillation Level]\nHIGH");
    expect(out).toContain("[Pattern-Distillation]\nstrong distillation");
    expect(out).toContain("[Stability-Distillation]\nstrong distillation");
    expect(out).toContain("[Resilience-Distillation]\nstrong distillation");
    expect(out).toContain("[Immunity-Distillation]\nstrong distillation");
    expect(out).toContain("[Integration-Distillation]\nstrong integration distillation");
    expect(out).toContain("[Alignment-Distillation]\nstrong alignment distillation");
    expect(out).toContain("[Coherence-Distillation]\nstrong coherence distillation");
    expect(out).toContain("[Synthesis-Distillation]\nstrong synthesis distillation");
    expect(out).toContain("[Consolidation-Distillation]\nstrong consolidation distillation");
    expect(out).toContain("[Compression-Distillation]\nstrong compression distillation");
    expect(out).toContain("[Reduction-Distillation]\nstrong reduction distillation");
    expect(out).toContain("[Extraction-Distillation]\nstrong extraction distillation");
    expect(out).toContain("[Meta-Distillation Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong pattern distillation");
    expect(out).toContain("- strong resilience distillation");
    expect(out).toContain("- strong synthesis distillation");
    expect(out).toContain("[Meta-Distillation Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Distillation Risks]\n(none)");
    expect(out).toContain("[Meta-Distillation Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-distillation is strong, with strong pattern-, resilience-, and synthesis-distillation.",
    );
    expect(out).not.toContain("Immunity-distillation remains");
  });

  it("strong pattern-distillation scenario: all HIGH + improving → 'strong distillation', driver, and the capstone PEAK projection", () => {
    const out = craft({ direction: "improving" });

    expect(out).toContain("[Pattern-Distillation]\nstrong distillation");
    expect(out).toContain("- strong pattern distillation");
    // Capstone: improving from a HIGH level projects through VERY-HIGH to PEAK.
    expect(out).toContain("[Meta-Distillation Trajectory]\nhigh → very-high → peak (projected)");
  });

  it("partial immunity-distillation scenario: meta-immunity level LOW-MEDIUM → 'partial distillation' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Distillation]\npartial distillation");
    expect(out).toContain("- partial immunity distillation");
    expect(out).toContain("- strengthen immunity distillation");
  });

  it("strong synthesis-distillation scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis distillation' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Distillation]\nstrong synthesis distillation");
    expect(out).toContain("- strong synthesis distillation");
  });

  it("summary correctness: strong + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-distillation is strong, with strong pattern-,
    //    resilience-, and synthesis-distillation. Immunity-distillation
    //    remains partial and may disrupt overall distillation."
    const out = craft({
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-distillation is strong, with strong pattern-, resilience-, and synthesis-distillation. Immunity-distillation remains partial and may disrupt overall distillation.",
    );
  });
});
