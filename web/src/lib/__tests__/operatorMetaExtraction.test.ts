// Card 88 — Operator Meta-Extraction engine unit tests.
//
// Card 88 extracts the actionable core from the *levels* of all eleven
// meta-layers — meta-pattern (77) … meta-reduction (87). The baseline
// test runs the real operator chain end-to-end (so header drift in any
// upstream card is caught); the scenario tests craft minimal upstream
// strings with explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-
// extraction (+ the VERY-HIGH projected trajectory), partial immunity-
// extraction, strong synthesis-extraction, and summary correctness.

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
function fullChainExtraction(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  return buildOperatorMetaExtraction(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction,
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
  metaCompression?: string; metaReduction?: string;
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

  return buildOperatorMetaExtraction(
    operatorState, operatorDiff, "", "", "", "", "", "",
    mp, ms, mr, mi, mn, ma, mc, my, mo, mz, md,
  );
}

describe("Card 88 — buildOperatorMetaExtraction", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-extraction + all-strong extractions + steady summary", () => {
    const out = fullChainExtraction("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Extraction ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Extraction Level]")).toBeGreaterThan(idx("=== Operator Meta-Extraction ==="));
    expect(idx("[Pattern-Extraction]")).toBeGreaterThan(idx("[Meta-Extraction Level]"));
    expect(idx("[Stability-Extraction]")).toBeGreaterThan(idx("[Pattern-Extraction]"));
    expect(idx("[Resilience-Extraction]")).toBeGreaterThan(idx("[Stability-Extraction]"));
    expect(idx("[Immunity-Extraction]")).toBeGreaterThan(idx("[Resilience-Extraction]"));
    expect(idx("[Integration-Extraction]")).toBeGreaterThan(idx("[Immunity-Extraction]"));
    expect(idx("[Alignment-Extraction]")).toBeGreaterThan(idx("[Integration-Extraction]"));
    expect(idx("[Coherence-Extraction]")).toBeGreaterThan(idx("[Alignment-Extraction]"));
    expect(idx("[Synthesis-Extraction]")).toBeGreaterThan(idx("[Coherence-Extraction]"));
    expect(idx("[Consolidation-Extraction]")).toBeGreaterThan(idx("[Synthesis-Extraction]"));
    expect(idx("[Compression-Extraction]")).toBeGreaterThan(idx("[Consolidation-Extraction]"));
    expect(idx("[Reduction-Extraction]")).toBeGreaterThan(idx("[Compression-Extraction]"));
    expect(idx("[Meta-Extraction Trajectory]")).toBeGreaterThan(idx("[Reduction-Extraction]"));
    expect(idx("[Meta-Extraction Drivers]")).toBeGreaterThan(idx("[Meta-Extraction Trajectory]"));
    expect(idx("[Meta-Extraction Inhibitors]")).toBeGreaterThan(idx("[Meta-Extraction Drivers]"));
    expect(idx("[Meta-Extraction Risks]")).toBeGreaterThan(idx("[Meta-Extraction Inhibitors]"));
    expect(idx("[Meta-Extraction Reinforcement]")).toBeGreaterThan(idx("[Meta-Extraction Risks]"));
    expect(idx("[Meta-Extraction Decay]")).toBeGreaterThan(idx("[Meta-Extraction Reinforcement]"));
    expect(idx("[Operator Meta-Extraction Summary]")).toBeGreaterThan(idx("[Meta-Extraction Decay]"));

    // All-optimal baseline — every extracted facet reads strong.
    expect(out).toContain("[Meta-Extraction Level]\nHIGH");
    expect(out).toContain("[Pattern-Extraction]\nstrong extraction");
    expect(out).toContain("[Stability-Extraction]\nstrong extraction");
    expect(out).toContain("[Resilience-Extraction]\nstrong extraction");
    expect(out).toContain("[Immunity-Extraction]\nstrong extraction");
    expect(out).toContain("[Integration-Extraction]\nstrong integration extraction");
    expect(out).toContain("[Alignment-Extraction]\nstrong alignment extraction");
    expect(out).toContain("[Coherence-Extraction]\nstrong coherence extraction");
    expect(out).toContain("[Synthesis-Extraction]\nstrong synthesis extraction");
    expect(out).toContain("[Consolidation-Extraction]\nstrong consolidation extraction");
    expect(out).toContain("[Compression-Extraction]\nstrong compression extraction");
    expect(out).toContain("[Reduction-Extraction]\nstrong reduction extraction");
    expect(out).toContain("[Meta-Extraction Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong pattern extraction");
    expect(out).toContain("- strong resilience extraction");
    expect(out).toContain("- strong synthesis extraction");
    expect(out).toContain("[Meta-Extraction Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Extraction Risks]\n(none)");
    expect(out).toContain("[Meta-Extraction Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-extraction is steady, with strong pattern-, resilience-, and synthesis-extraction.",
    );
    expect(out).not.toContain("Immunity-extraction remains");
  });

  it("strong pattern-extraction scenario: all MEDIUM-HIGH + improving → 'strong extraction', driver, and the VERY-HIGH projection", () => {
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
      metaReduction:     "MEDIUM-HIGH",
    });

    expect(out).toContain("[Pattern-Extraction]\nstrong extraction");
    expect(out).toContain("- strong pattern extraction");
    // Forward projection from a MEDIUM-HIGH level reaches the VERY-HIGH band.
    expect(out).toContain("[Meta-Extraction Trajectory]\nmedium-high → high → very-high (projected)");
  });

  it("partial immunity-extraction scenario: meta-immunity level LOW-MEDIUM → 'partial extraction' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Extraction]\npartial extraction");
    expect(out).toContain("- partial immunity extraction");
    expect(out).toContain("- strengthen immunity extraction");
  });

  it("strong synthesis-extraction scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis extraction' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Extraction]\nstrong synthesis extraction");
    expect(out).toContain("- strong synthesis extraction");
  });

  it("summary correctness: improving + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-extraction is strengthening, with strong
    //    pattern-, resilience-, and synthesis-extraction. Immunity-
    //    extraction remains partial and may disrupt overall extraction."
    const out = craft({
      direction:      "improving",
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-extraction is strengthening, with strong pattern-, resilience-, and synthesis-extraction. Immunity-extraction remains partial and may disrupt overall extraction.",
    );
  });
});
