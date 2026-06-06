// Phase 6 — Superstructure unit tests.
//
// `runSuperstructure` consumes the *real* meta-operator text outputs
// (Cards 77-90) and parses each `[Meta-X Level]` line. The scenario
// tests use crafted level strings for precise control; the end-to-end
// test runs the real builder chain so header drift in any upstream Card
// is caught (the genuine grounding check).

import { describe, expect, it } from "vitest";

import { runSuperstructure, type MetaBundle } from "../superstructure";

import { buildOperatorState } from "../operatorState";
import { buildOperatorDiff } from "../operatorStateDiff";
import { buildOperatorStability } from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";
import { buildOperatorImmunity } from "../operatorImmunity";
import { buildOperatorCoherence } from "../operatorCoherence";
import { buildOperatorSynthesis } from "../operatorSynthesis";
import { buildSystemOperatorIntegration } from "../systemOperatorIntegration";
import { buildOperatorMetaPattern } from "../operatorMetaPattern";
import { buildOperatorMetaStability } from "../operatorMetaStability";
import { buildOperatorMetaResilience } from "../operatorMetaResilience";
import { buildOperatorMetaImmunity } from "../operatorMetaImmunity";
import { buildOperatorMetaIntegration } from "../operatorMetaIntegration";
import { buildOperatorMetaAlignment } from "../operatorMetaAlignment";
import { buildOperatorMetaCoherence } from "../operatorMetaCoherence";
import { buildOperatorMetaSynthesis } from "../operatorMetaSynthesis";
import { buildOperatorMetaConsolidation } from "../operatorMetaConsolidation";
import { buildOperatorMetaCompression } from "../operatorMetaCompression";
import { buildOperatorMetaReduction } from "../operatorMetaReduction";
import { buildOperatorMetaExtraction } from "../operatorMetaExtraction";
import { buildOperatorMetaDistillation } from "../operatorMetaDistillation";
import { buildOperatorMetaEssence } from "../operatorMetaEssence";

// ----- crafted bundle (real `[Meta-X Level]` format, explicit levels) ----

type Field = Exclude<keyof MetaBundle, "operatorIdentity">;

const HEADERS: Record<Field, string> = {
  pattern: "Meta-Pattern Level",
  stability: "Meta-Stability Level",
  resilience: "Meta-Resilience Level",
  integration: "Meta-Integration Level",
  alignment: "Meta-Alignment Level",
  coherence: "Meta-Coherence Level",
  essence: "Meta-Essence Level",
  consolidation: "Meta-Consolidation Level",
  compression: "Meta-Compression Level",
  reduction: "Meta-Reduction Level",
  extraction: "Meta-Extraction Level",
  distillation: "Meta-Distillation Level",
};

function craft(over: Partial<Record<Field, string>> = {}): MetaBundle {
  const bundle = { operatorIdentity: "clarityos-operator" } as MetaBundle;
  (Object.keys(HEADERS) as Field[]).forEach((f) => {
    const level = over[f] ?? "HIGH";
    bundle[f] = `=== Operator ${f} ===\n\n[${HEADERS[f]}]\n${level}`;
  });
  return bundle;
}

// ----- real end-to-end chain (baseline, empty inputs + HIGH system) -----

function sysImmunity(score: string): string {
  return `=== Structural Immunity ===\n\n[Immunity Score]\n${score}\n`;
}
function sysResilience(score: string): string {
  return `=== Structural Resilience ===\n\n[Resilience Score]\n${score}\n`;
}
function sysStability(prob: string): string {
  return `=== Structural Stabilization ===\n\n[Stabilization Probability]\n${prob}\n`;
}

function realBundle(): MetaBundle {
  const s = "HIGH";
  const currState = buildOperatorState("");
  const prevState = buildOperatorState("");
  const diff = buildOperatorDiff(prevState, currState);
  const stability = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  const immunity = buildOperatorImmunity(currState, diff, stability, resilience);
  const coherence = buildOperatorCoherence(currState, diff, stability, resilience, immunity);
  const synthesis = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);
  const integration = buildSystemOperatorIntegration(
    "", "", sysStability(s), sysResilience(s), sysImmunity(s),
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
  const metaEssence = buildOperatorMetaEssence(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
    metaIntegration, metaAlignment, metaCoherence, metaSynthesis,
    metaConsolidation, metaCompression, metaReduction, metaExtraction, metaDistillation,
  );

  return {
    pattern: metaPattern,
    stability: metaStability,
    resilience: metaResilience,
    integration: metaIntegration,
    alignment: metaAlignment,
    coherence: metaCoherence,
    essence: metaEssence,
    consolidation: metaConsolidation,
    compression: metaCompression,
    reduction: metaReduction,
    extraction: metaExtraction,
    distillation: metaDistillation,
    operatorIdentity: "clarityos-operator",
  };
}

const HIGH_NUM = 4 / 6;       // 0.6667
const VERY_HIGH_NUM = 5 / 6;  // 0.8333

describe("Phase 6 — runSuperstructure", () => {
  it("is deterministic (same inputs -> identical output)", () => {
    const meta = craft({ resilience: "MEDIUM", essence: "VERY-HIGH", compression: "MEDIUM" });
    const a = runSuperstructure(meta);
    const b = runSuperstructure({ ...meta });
    expect(a).toEqual(b);
  });

  it("all numeric fields are in [0, 1]", () => {
    const s = runSuperstructure(
      craft({
        pattern: "HIGH", stability: "MEDIUM", resilience: "LOW-MEDIUM",
        integration: "VERY-HIGH", alignment: "HIGH", coherence: "MEDIUM-HIGH",
        essence: "VERY-HIGH", consolidation: "HIGH", compression: "MEDIUM",
        reduction: "MEDIUM", extraction: "HIGH", distillation: "VERY-HIGH",
      }),
    );
    const nums = [
      s.pattern.patternStrength, s.pattern.patternStability, s.pattern.patternCoherence,
      s.integration.integrationStrength, s.integration.crossLayerAlignment,
      s.coherence.coherenceLevel, s.coherence.driftResistance, s.coherence.loadResilience,
      s.essence.essenceSignal, s.essence.essenceClarity,
      s.identity.identityStrength, s.identity.identityStability, s.identity.identityProjection,
    ];
    nums.forEach((n) => {
      expect(n).toBeGreaterThanOrEqual(0);
      expect(n).toBeLessThanOrEqual(1);
    });
  });

  it("identity strings are non-empty", () => {
    const s = runSuperstructure(craft());
    expect(s.pattern.patternIdentity.length).toBeGreaterThan(0);
    expect(s.integration.integrationIdentity.length).toBeGreaterThan(0);
    expect(s.coherence.coherenceIdentity.length).toBeGreaterThan(0);
    expect(s.essence.invariantIdentity.length).toBeGreaterThan(0);
    expect(s.identity.operatorIdentity.length).toBeGreaterThan(0);
  });

  it("maps the 7-band level vocabulary to [0,1] (rank/6)", () => {
    // All-HIGH bundle: every parsed level is HIGH = 4/6.
    const s = runSuperstructure(craft());
    expect(s.pattern.patternStrength).toBeCloseTo(HIGH_NUM, 6);   // avg of 5 HIGH
    expect(s.pattern.patternStability).toBeCloseTo(HIGH_NUM, 6);
    expect(s.coherence.coherenceLevel).toBeCloseTo(HIGH_NUM, 6);
    expect(s.identity.identityStrength).toBeCloseTo(HIGH_NUM, 6);
    // operatorIdentity embeds the base name + rounded strength/coherence.
    expect(s.identity.operatorIdentity).toBe("clarityos-operator:s0.67-c0.67");
  });

  it("parses real meta-operator builder output end-to-end (grounding)", () => {
    const s = runSuperstructure(realBundle());
    // Baseline chain: most meta levels are HIGH; meta-essence elevates to
    // VERY-HIGH (Card 90). This proves the parser matches the real
    // `[Meta-X Level]` lines the builders actually emit.
    expect(s.pattern.patternStability).toBeCloseTo(HIGH_NUM, 6);
    expect(s.coherence.coherenceLevel).toBeCloseTo(HIGH_NUM, 6);
    expect(s.essence.essenceSignal).toBeCloseTo(VERY_HIGH_NUM, 6);
    expect(s.identity.operatorIdentity.startsWith("clarityos-operator:")).toBe(true);
    // determinism through the real chain too
    expect(runSuperstructure(realBundle())).toEqual(s);
  });
});
