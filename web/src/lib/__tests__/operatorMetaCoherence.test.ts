// Card 83 — Operator Meta-Coherence engine unit tests.
//
// Card 83 harmonises the *levels* of synthesis (75) and the five higher
// meta-layers — meta-stability (78), meta-resilience (79), meta-
// immunity (80), meta-integration (81), meta-alignment (82). The
// baseline test runs the real operator chain end-to-end (so header
// drift in any upstream card is caught); the scenario tests craft
// minimal upstream strings with explicit levels for precise control
// over each per-dimension word.
//
// Tests cover the five spec scenarios: baseline, strong synthesis-
// coherence, partial immunity-coherence, strong integration-coherence,
// and summary correctness.

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
function fullChainCoherence(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  return buildOperatorMetaCoherence(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity, metaIntegration, metaAlignment,
  );
}

// Crafted upstream — builds the minimal sections the helper parses,
// with every facet level explicitly set. Defaults are all-optimal.
interface CraftOpts {
  load?: string; drift?: string; clarity?: string; pressure?: string;
  direction?: "improving" | "stable" | "deteriorating";
  synthesis?: string; metaStability?: string; metaResilience?: string;
  metaImmunity?: string; metaIntegration?: string; metaAlignment?: string;
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

  const synthesis       = `=== Operator Synthesis ===\n\n[Synthesis Level]\n${o.synthesis ?? "HIGH"}`;
  const metaStability   = `=== Operator Meta-Stability ===\n\n[Meta-Stability Level]\n${o.metaStability ?? "HIGH"}`;
  const metaResilience  = `=== Operator Meta-Resilience ===\n\n[Meta-Resilience Level]\n${o.metaResilience ?? "HIGH"}`;
  const metaImmunity    = `=== Operator Meta-Immunity ===\n\n[Meta-Immunity Level]\n${o.metaImmunity ?? "HIGH"}`;
  const metaIntegration = `=== Operator Meta-Integration ===\n\n[Meta-Integration Level]\n${o.metaIntegration ?? "HIGH"}`;
  const metaAlignment   = `=== Operator Meta-Alignment ===\n\n[Meta-Alignment Level]\n${o.metaAlignment ?? "HIGH"}`;

  return buildOperatorMetaCoherence(
    operatorState, operatorDiff, "", "", "", "", synthesis, "", "",
    metaStability, metaResilience, metaImmunity, metaIntegration, metaAlignment,
  );
}

describe("Card 83 — buildOperatorMetaCoherence", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-coherence + all-strong coherences + steady summary", () => {
    const out = fullChainCoherence("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Coherence ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Coherence Level]")).toBeGreaterThan(idx("=== Operator Meta-Coherence ==="));
    expect(idx("[Synthesis-Coherence]")).toBeGreaterThan(idx("[Meta-Coherence Level]"));
    expect(idx("[Stability-Coherence]")).toBeGreaterThan(idx("[Synthesis-Coherence]"));
    expect(idx("[Resilience-Coherence]")).toBeGreaterThan(idx("[Stability-Coherence]"));
    expect(idx("[Immunity-Coherence]")).toBeGreaterThan(idx("[Resilience-Coherence]"));
    expect(idx("[Integration-Coherence]")).toBeGreaterThan(idx("[Immunity-Coherence]"));
    expect(idx("[Alignment-Coherence]")).toBeGreaterThan(idx("[Integration-Coherence]"));
    expect(idx("[Meta-Coherence Trajectory]")).toBeGreaterThan(idx("[Alignment-Coherence]"));
    expect(idx("[Meta-Coherence Drivers]")).toBeGreaterThan(idx("[Meta-Coherence Trajectory]"));
    expect(idx("[Meta-Coherence Inhibitors]")).toBeGreaterThan(idx("[Meta-Coherence Drivers]"));
    expect(idx("[Meta-Coherence Risks]")).toBeGreaterThan(idx("[Meta-Coherence Inhibitors]"));
    expect(idx("[Meta-Coherence Reinforcement]")).toBeGreaterThan(idx("[Meta-Coherence Risks]"));
    expect(idx("[Meta-Coherence Decay]")).toBeGreaterThan(idx("[Meta-Coherence Reinforcement]"));
    expect(idx("[Operator Meta-Coherence Summary]")).toBeGreaterThan(idx("[Meta-Coherence Decay]"));

    // All-optimal baseline — every harmonised facet reads strong.
    expect(out).toContain("[Meta-Coherence Level]\nHIGH");
    expect(out).toContain("[Synthesis-Coherence]\nstrong coherence");
    expect(out).toContain("[Stability-Coherence]\nstrong coherence");
    expect(out).toContain("[Resilience-Coherence]\nstrong coherence");
    expect(out).toContain("[Immunity-Coherence]\nstrong coherence");
    expect(out).toContain("[Integration-Coherence]\nstrong integration coherence");
    expect(out).toContain("[Alignment-Coherence]\nstrong alignment coherence");
    expect(out).toContain("[Meta-Coherence Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong synthesis coherence");
    expect(out).toContain("- strong resilience coherence");
    expect(out).toContain("- strong integration coherence");
    expect(out).toContain("[Meta-Coherence Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Coherence Risks]\n(none)");
    expect(out).toContain("[Meta-Coherence Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-coherence is steady, with strong synthesis-, resilience-, and integration-coherence.",
    );
    expect(out).not.toContain("Immunity-coherence remains");
  });

  it("strong synthesis-coherence scenario: synthesis level MEDIUM-HIGH → 'strong coherence' + driver", () => {
    const out = craft({ synthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Coherence]\nstrong coherence");
    expect(out).toContain("- strong synthesis coherence");
  });

  it("partial immunity-coherence scenario: meta-immunity level LOW-MEDIUM → 'partial coherence' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Coherence]\npartial coherence");
    expect(out).toContain("- partial immunity coherence");
    expect(out).toContain("- strengthen immunity coherence");
  });

  it("strong integration-coherence scenario: meta-integration level MEDIUM-HIGH → 'strong integration coherence' + driver", () => {
    const out = craft({ metaIntegration: "MEDIUM-HIGH" });

    expect(out).toContain("[Integration-Coherence]\nstrong integration coherence");
    expect(out).toContain("- strong integration coherence");
  });

  it("summary correctness: improving + strong synthesis/resilience/integration + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-coherence is strengthening, with strong
    //    synthesis-, resilience-, and integration-coherence. Immunity-
    //    coherence remains partial and may disrupt overall coherence."
    const out = craft({
      direction:       "improving",
      synthesis:       "HIGH",
      metaResilience:  "HIGH",
      metaIntegration: "HIGH",
      metaImmunity:    "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-coherence is strengthening, with strong synthesis-, resilience-, and integration-coherence. Immunity-coherence remains partial and may disrupt overall coherence.",
    );
  });
});
