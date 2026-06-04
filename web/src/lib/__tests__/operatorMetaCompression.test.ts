// Card 86 — Operator Meta-Compression engine unit tests.
//
// Card 86 compresses the *levels* of all nine meta-layers — meta-
// pattern (77) … meta-consolidation (85). The baseline test runs the
// real operator chain end-to-end (so header drift in any upstream card
// is caught); the scenario tests craft minimal upstream strings with
// explicit levels for precise control.
//
// Tests cover the five spec scenarios: baseline, strong pattern-
// compression (+ the VERY-HIGH projected trajectory), partial immunity-
// compression, strong synthesis-compression, and summary correctness.

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
function fullChainCompression(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  return buildOperatorMetaCompression(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis, metaConsolidation,
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

  return buildOperatorMetaCompression(
    operatorState, operatorDiff, "", "", "", "", "", "",
    mp, ms, mr, mi, mn, ma, mc, my, mo,
  );
}

describe("Card 86 — buildOperatorMetaCompression", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-compression + all-strong compressions + steady summary", () => {
    const out = fullChainCompression("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Compression ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Compression Level]")).toBeGreaterThan(idx("=== Operator Meta-Compression ==="));
    expect(idx("[Pattern-Compression]")).toBeGreaterThan(idx("[Meta-Compression Level]"));
    expect(idx("[Stability-Compression]")).toBeGreaterThan(idx("[Pattern-Compression]"));
    expect(idx("[Resilience-Compression]")).toBeGreaterThan(idx("[Stability-Compression]"));
    expect(idx("[Immunity-Compression]")).toBeGreaterThan(idx("[Resilience-Compression]"));
    expect(idx("[Integration-Compression]")).toBeGreaterThan(idx("[Immunity-Compression]"));
    expect(idx("[Alignment-Compression]")).toBeGreaterThan(idx("[Integration-Compression]"));
    expect(idx("[Coherence-Compression]")).toBeGreaterThan(idx("[Alignment-Compression]"));
    expect(idx("[Synthesis-Compression]")).toBeGreaterThan(idx("[Coherence-Compression]"));
    expect(idx("[Consolidation-Compression]")).toBeGreaterThan(idx("[Synthesis-Compression]"));
    expect(idx("[Meta-Compression Trajectory]")).toBeGreaterThan(idx("[Consolidation-Compression]"));
    expect(idx("[Meta-Compression Drivers]")).toBeGreaterThan(idx("[Meta-Compression Trajectory]"));
    expect(idx("[Meta-Compression Inhibitors]")).toBeGreaterThan(idx("[Meta-Compression Drivers]"));
    expect(idx("[Meta-Compression Risks]")).toBeGreaterThan(idx("[Meta-Compression Inhibitors]"));
    expect(idx("[Meta-Compression Reinforcement]")).toBeGreaterThan(idx("[Meta-Compression Risks]"));
    expect(idx("[Meta-Compression Decay]")).toBeGreaterThan(idx("[Meta-Compression Reinforcement]"));
    expect(idx("[Operator Meta-Compression Summary]")).toBeGreaterThan(idx("[Meta-Compression Decay]"));

    // All-optimal baseline — every compressed facet reads strong.
    expect(out).toContain("[Meta-Compression Level]\nHIGH");
    expect(out).toContain("[Pattern-Compression]\nstrong compression");
    expect(out).toContain("[Stability-Compression]\nstrong compression");
    expect(out).toContain("[Resilience-Compression]\nstrong compression");
    expect(out).toContain("[Immunity-Compression]\nstrong compression");
    expect(out).toContain("[Integration-Compression]\nstrong integration compression");
    expect(out).toContain("[Alignment-Compression]\nstrong alignment compression");
    expect(out).toContain("[Coherence-Compression]\nstrong coherence compression");
    expect(out).toContain("[Synthesis-Compression]\nstrong synthesis compression");
    expect(out).toContain("[Consolidation-Compression]\nstrong consolidation compression");
    expect(out).toContain("[Meta-Compression Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong pattern compression");
    expect(out).toContain("- strong resilience compression");
    expect(out).toContain("- strong synthesis compression");
    expect(out).toContain("[Meta-Compression Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Compression Risks]\n(none)");
    expect(out).toContain("[Meta-Compression Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-compression is steady, with strong pattern-, resilience-, and synthesis-compression.",
    );
    expect(out).not.toContain("Immunity-compression remains");
  });

  it("strong pattern-compression scenario: all MEDIUM-HIGH + improving → 'strong compression', driver, and the VERY-HIGH projection", () => {
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
    });

    expect(out).toContain("[Pattern-Compression]\nstrong compression");
    expect(out).toContain("- strong pattern compression");
    // Forward projection from a MEDIUM-HIGH level reaches the VERY-HIGH band.
    expect(out).toContain("[Meta-Compression Trajectory]\nmedium-high → high → very-high (projected)");
  });

  it("partial immunity-compression scenario: meta-immunity level LOW-MEDIUM → 'partial compression' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Compression]\npartial compression");
    expect(out).toContain("- partial immunity compression");
    expect(out).toContain("- strengthen immunity compression");
  });

  it("strong synthesis-compression scenario: meta-synthesis level MEDIUM-HIGH → 'strong synthesis compression' + driver", () => {
    const out = craft({ metaSynthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Compression]\nstrong synthesis compression");
    expect(out).toContain("- strong synthesis compression");
  });

  it("summary correctness: improving + strong pattern/resilience/synthesis + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-compression is strengthening, with strong
    //    pattern-, resilience-, and synthesis-compression. Immunity-
    //    compression remains partial and may disrupt overall
    //    compression."
    const out = craft({
      direction:      "improving",
      metaPattern:    "HIGH",
      metaResilience: "HIGH",
      metaSynthesis:  "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-compression is strengthening, with strong pattern-, resilience-, and synthesis-compression. Immunity-compression remains partial and may disrupt overall compression.",
    );
  });
});
