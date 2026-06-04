// Card 81 — Operator Meta-Integration engine unit tests.
//
// Card 81 integrates the *levels* of the upstream meta-layers
// (coherence 74, synthesis 75, meta-pattern 77, meta-stability 78,
// meta-resilience 79, meta-immunity 80) rather than the raw operator
// dims. The baseline test runs the real operator chain end-to-end (so
// header drift in any upstream card is caught); the scenario tests
// craft minimal upstream strings with explicit levels for precise
// control over each per-dimension word — combinations like "synthesis
// strong + immunity partial" are independent facets here and would not
// co-occur through the natural chain.
//
// Tests cover the five spec scenarios: baseline, strong synthesis-
// integration, partial immunity-integration, stable pattern-
// integration, and summary correctness.

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
function fullChainIntegration(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  return buildOperatorMetaIntegration(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity,
  );
}

// Crafted upstream — builds the minimal sections the helper parses,
// with every meta-layer level explicitly set. Defaults are the all-
// optimal baseline.
interface CraftOpts {
  load?: string; drift?: string; clarity?: string; pressure?: string;
  direction?: "improving" | "stable" | "deteriorating";
  coherence?: string; synthesis?: string; metaPattern?: string;
  metaStability?: string; metaResilience?: string; metaImmunity?: string;
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

  const coherence      = `=== Operator Coherence ===\n\n[Coherence Level]\n${o.coherence ?? "HIGH"}`;
  const synthesis      = `=== Operator Synthesis ===\n\n[Synthesis Level]\n${o.synthesis ?? "HIGH"}`;
  const metaPattern    = `=== Operator Meta-Pattern ===\n\n[Meta-Pattern Level]\n${o.metaPattern ?? "HIGH"}`;
  const metaStability  = `=== Operator Meta-Stability ===\n\n[Meta-Stability Level]\n${o.metaStability ?? "HIGH"}`;
  const metaResilience = `=== Operator Meta-Resilience ===\n\n[Meta-Resilience Level]\n${o.metaResilience ?? "HIGH"}`;
  const metaImmunity   = `=== Operator Meta-Immunity ===\n\n[Meta-Immunity Level]\n${o.metaImmunity ?? "HIGH"}`;

  return buildOperatorMetaIntegration(
    operatorState, operatorDiff, "", "", "", coherence, synthesis, "",
    metaPattern, metaStability, metaResilience, metaImmunity,
  );
}

describe("Card 81 — buildOperatorMetaIntegration", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-integration + all-strong integrations + steady summary", () => {
    const out = fullChainIntegration("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Integration ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Integration Level]")).toBeGreaterThan(idx("=== Operator Meta-Integration ==="));
    expect(idx("[Coherence-Integration]")).toBeGreaterThan(idx("[Meta-Integration Level]"));
    expect(idx("[Synthesis-Integration]")).toBeGreaterThan(idx("[Coherence-Integration]"));
    expect(idx("[Stability-Integration]")).toBeGreaterThan(idx("[Synthesis-Integration]"));
    expect(idx("[Resilience-Integration]")).toBeGreaterThan(idx("[Stability-Integration]"));
    expect(idx("[Immunity-Integration]")).toBeGreaterThan(idx("[Resilience-Integration]"));
    expect(idx("[Pattern-Integration]")).toBeGreaterThan(idx("[Immunity-Integration]"));
    expect(idx("[Meta-Integration Trajectory]")).toBeGreaterThan(idx("[Pattern-Integration]"));
    expect(idx("[Meta-Integration Drivers]")).toBeGreaterThan(idx("[Meta-Integration Trajectory]"));
    expect(idx("[Meta-Integration Inhibitors]")).toBeGreaterThan(idx("[Meta-Integration Drivers]"));
    expect(idx("[Meta-Integration Risks]")).toBeGreaterThan(idx("[Meta-Integration Inhibitors]"));
    expect(idx("[Meta-Integration Reinforcement]")).toBeGreaterThan(idx("[Meta-Integration Risks]"));
    expect(idx("[Meta-Integration Decay]")).toBeGreaterThan(idx("[Meta-Integration Reinforcement]"));
    expect(idx("[Operator Meta-Integration Summary]")).toBeGreaterThan(idx("[Meta-Integration Decay]"));

    // All-optimal baseline — every integrated facet reads strong.
    expect(out).toContain("[Meta-Integration Level]\nHIGH");
    expect(out).toContain("[Coherence-Integration]\nstrong integration");
    expect(out).toContain("[Synthesis-Integration]\nstrong integration");
    expect(out).toContain("[Stability-Integration]\nstrong stability");
    expect(out).toContain("[Resilience-Integration]\nstrong resilience");
    expect(out).toContain("[Immunity-Integration]\nstrong immunity");
    expect(out).toContain("[Pattern-Integration]\nstable pattern integration");
    expect(out).toContain("[Meta-Integration Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong synthesis integration");
    expect(out).toContain("- strong resilience integration");
    expect(out).toContain("- stable pattern integration");
    expect(out).toContain("[Meta-Integration Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Integration Risks]\n(none)");
    expect(out).toContain("[Meta-Integration Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-integration is steady, with strong synthesis- and resilience-integration.",
    );
    expect(out).not.toContain("Immunity-integration remains");
  });

  it("strong synthesis-integration scenario: synthesis level MEDIUM-HIGH → 'strong integration' + driver", () => {
    const out = craft({ synthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Integration]\nstrong integration");
    expect(out).toContain("- strong synthesis integration");
  });

  it("partial immunity-integration scenario: meta-immunity level LOW-MEDIUM → 'partial immunity' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW-MEDIUM" });

    expect(out).toContain("[Immunity-Integration]\npartial immunity");
    expect(out).toContain("- partial immunity integration");
    expect(out).toContain("- strengthen immunity integration");
  });

  it("stable pattern-integration scenario: meta-pattern level MEDIUM → 'stable pattern integration' + driver", () => {
    const out = craft({ metaPattern: "MEDIUM" });

    expect(out).toContain("[Pattern-Integration]\nstable pattern integration");
    expect(out).toContain("- stable pattern integration");
  });

  it("summary correctness: improving + strong synthesis/resilience + partial immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-integration is strengthening, with strong
    //    synthesis- and resilience-integration. Immunity-integration
    //    remains partial and may disrupt overall integration."
    const out = craft({
      direction:      "improving",
      synthesis:      "HIGH",
      metaResilience: "HIGH",
      metaImmunity:   "LOW-MEDIUM",
    });

    expect(out).toContain(
      "Operator meta-integration is strengthening, with strong synthesis- and resilience-integration. Immunity-integration remains partial and may disrupt overall integration.",
    );
  });
});
