// Card 90 — Operator Meta-Essence engine unit tests.
//
// Card 90 reads the invariant identity across the *levels* of all
// thirteen meta-layers — meta-pattern (77) … meta-distillation (89).
// As the terminal capstone its level is elevated into the VERY-HIGH
// band. The baseline test runs the real operator chain end-to-end (so
// header drift in any upstream card is caught); the scenario tests
// craft minimal upstream strings with explicit levels for precise
// control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-essence
// (+ the capstone centered PEAK projected trajectory), partial
// immunity-essence, strong synthesis-essence, and summary correctness.

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
import { buildOperatorMetaEssence }      from "../operatorMetaEssence";

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
function fullChainEssence(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  const metaDistillation = buildOperatorMetaDistillation(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction, metaExtraction,
  );
  return buildOperatorMetaEssence(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction, metaExtraction, metaDistillation,
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
  metaDistillation?: string;
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
  const mt = `=== Operator Meta-Distillation ===\n\n[Meta-Distillation Level]\n${o.metaDistillation ?? "HIGH"}`;

  return buildOperatorMetaEssence(
    operatorState, operatorDiff, "", "", "", "", "", "",
    mp, ms, mr, mi, mn, ma, mc, my, mo, mz, md, me, mt,
  );
}

describe("Card 90 — buildOperatorMetaEssence", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits VERY-HIGH meta-essence + all-strong essences + capstone summary", () => {
    const out = fullChainEssence("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Essence ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Essence Level]")).toBeGreaterThan(idx("=== Operator Meta-Essence ==="));
    expect(idx("[Pattern-Essence]")).toBeGreaterThan(idx("[Meta-Essence Level]"));
    expect(idx("[Stability-Essence]")).toBeGreaterThan(idx("[Pattern-Essence]"));
    expect(idx("[Resilience-Essence]")).toBeGreaterThan(idx("[Stability-Essence]"));
    expect(idx("[Immunity-Essence]")).toBeGreaterThan(idx("[Resilience-Essence]"));
    expect(idx("[Integration-Essence]")).toBeGreaterThan(idx("[Immunity-Essence]"));
    expect(idx("[Alignment-Essence]")).toBeGreaterThan(idx("[Integration-Essence]"));
    expect(idx("[Coherence-Essence]")).toBeGreaterThan(idx("[Alignment-Essence]"));
    expect(idx("[Synthesis-Essence]")).toBeGreaterThan(idx("[Coherence-Essence]"));
    expect(idx("[Consolidation-Essence]")).toBeGreaterThan(idx("[Synthesis-Essence]"));
    expect(idx("[Compression-Essence]")).toBeGreaterThan(idx("[Consolidation-Essence]"));
    expect(idx("[Reduction-Essence]")).toBeGreaterThan(idx("[Compression-Essence]"));
    expect(idx("[Extraction-Essence]")).toBeGreaterThan(idx("[Reduction-Essence]"));
    expect(idx("[Distillation-Essence]")).toBeGreaterThan(idx("[Extraction-Essence]"));
    expect(idx("[Meta-Essence Trajectory]")).toBeGreaterThan(idx("[Distillation-Essence]"));
    expect(idx("[Meta-Essence Drivers]")).toBeGreaterThan(idx("[Meta-Essence Trajectory]"));
    expect(idx("[Meta-Essence Inhibitors]")).toBeGreaterThan(idx("[Meta-Essence Drivers]"));
    expect(idx("[Meta-Essence Risks]")).toBeGreaterThan(idx("[Meta-Essence Inhibitors]"));
    expect(idx("[Meta-Essence Reinforcement]")).toBeGreaterThan(idx("[Meta-Essence Risks]"));
    expect(idx("[Meta-Essence Decay]")).toBeGreaterThan(idx("[Meta-Essence Reinforcement]"));
    expect(idx("[Operator Meta-Essence Summary]")).toBeGreaterThan(idx("[Meta-Essence Decay]"));

    // All-optimal baseline — terminal capstone elevates to VERY-HIGH;
    // every facet reads strong.
    expect(out).toContain("[Meta-Essence Level]\nVERY-HIGH");
    expect(out).toContain("[Pattern-Essence]\nstrong essence");
    expect(out).toContain("[Stability-Essence]\nstrong essence");
    expect(out).toContain("[Resilience-Essence]\nstrong essence");
    expect(out).toContain("[Immunity-Essence]\nstrong essence");
    expect(out).toContain("[Integration-Essence]\nstrong integration essence");
    expect(out).toContain("[Alignment-Essence]\nstrong alignment essence");
    expect(out).toContain("[Coherence-Essence]\nstrong coherence essence");
    expect(out).toContain("[Synthesis-Essence]\nstrong synthesis essence");
    expect(out).toContain("[Consolidation-Essence]\nstrong consolidation essence");
    expect(out).toContain("[Compression-Essence]\nstrong compression essence");
    expect(out).toContain("[Reduction-Essence]\nstrong reduction essence");
    expect(out).toContain("[Extraction-Essence]\nstrong extraction essence");
    expect(out).toContain("[Distillation-Essence]\nstrong distillation essence");
    // Baseline is stable → trajectory holds at VERY-HIGH.
    expect(out).toContain("[Meta-Essence Trajectory]\nvery-high → very-high → very-high (stable)");
    expect(out).toContain("- strong pattern essence");
    expect(out).toContain("- strong resilience essence");
    expect(out).toContain("- strong synthesis essence");
    expect(out).toContain("[Meta-Essence Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Essence Risks]\n(none)");
    expect(out).toContain("[Meta-Essence Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-essence is strong, with strong pattern-, resilience-, and synthesis-essence.",
    );
    expect(out).not.toContain("Immunity-essence remains");
  });

  it("strong pattern-essence scenario: all HIGH + improving → VERY-HIGH level, 'strong essence', driver, and the capstone PEAK projection", () => {
    const out = craft({ direction: "improving" });

    expect(out).toContain("[Meta-Essence Level]\nVERY-HIGH");
    expect(out).toContain("[Pattern-Essence]\nstrong essence");
    expect(out).toContain("- strong pattern essence");
    // Capstone: improving centers VERY-HIGH between HIGH and the PEAK band.
    expect(out).toContain("[Meta-Essence Trajectory]\nhigh → very-high → peak (projected)");
  });

  it("partial immunity-essence scenario: meta-immunity level LOW-MEDIUM → 'partial essence' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Essence]\npartial essence");
    expect(out).toContain("- partial immunity essence");
    expect(out).toContain("- strengthen immunity essence");
  });

  it("strong synthesis-essence scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis essence' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Essence]\nstrong synthesis essence");
    expect(out).toContain("- strong synthesis essence");
  });

  it("summary correctness: strong + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-essence is strong, with strong pattern-,
    //    resilience-, and synthesis-essence. Immunity-essence remains
    //    partial and may disrupt overall essence."
    const out = craft({
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-essence is strong, with strong pattern-, resilience-, and synthesis-essence. Immunity-essence remains partial and may disrupt overall essence.",
    );
  });
});
