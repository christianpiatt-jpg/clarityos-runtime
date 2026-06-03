// Card 82 — Operator Meta-Alignment engine unit tests.
//
// Card 82 aligns the *levels* of the upstream meta-layers (coherence
// 74, synthesis 75, meta-pattern 77, meta-stability 78, meta-resilience
// 79, meta-immunity 80) and caps on meta-integration (81). The baseline
// test runs the real operator chain end-to-end (so header drift in any
// upstream card is caught); the scenario tests craft minimal upstream
// strings with explicit levels for precise control over each per-
// dimension word.
//
// Tests cover the five spec scenarios: baseline, strong synthesis-
// alignment, weak immunity-alignment, stable pattern-alignment, and
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
function fullChainAlignment(prevInput: string, currInput: string, systemScore = "HIGH"): string {
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
  return buildOperatorMetaAlignment(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience, metaImmunity, metaIntegration,
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
  metaIntegration?: string;
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

  const coherence       = `=== Operator Coherence ===\n\n[Coherence Level]\n${o.coherence ?? "HIGH"}`;
  const synthesis       = `=== Operator Synthesis ===\n\n[Synthesis Level]\n${o.synthesis ?? "HIGH"}`;
  const metaPattern     = `=== Operator Meta-Pattern ===\n\n[Meta-Pattern Level]\n${o.metaPattern ?? "HIGH"}`;
  const metaStability   = `=== Operator Meta-Stability ===\n\n[Meta-Stability Level]\n${o.metaStability ?? "HIGH"}`;
  const metaResilience  = `=== Operator Meta-Resilience ===\n\n[Meta-Resilience Level]\n${o.metaResilience ?? "HIGH"}`;
  const metaImmunity    = `=== Operator Meta-Immunity ===\n\n[Meta-Immunity Level]\n${o.metaImmunity ?? "HIGH"}`;
  const metaIntegration = `=== Operator Meta-Integration ===\n\n[Meta-Integration Level]\n${o.metaIntegration ?? "HIGH"}`;

  return buildOperatorMetaAlignment(
    operatorState, operatorDiff, "", "", "", coherence, synthesis, "",
    metaPattern, metaStability, metaResilience, metaImmunity, metaIntegration,
  );
}

describe("Card 82 — buildOperatorMetaAlignment", () => {
  it("baseline (real chain, empty inputs + HIGH system) emits HIGH meta-alignment + all-strong alignments + steady summary", () => {
    const out = fullChainAlignment("", "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Alignment ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Alignment Level]")).toBeGreaterThan(idx("=== Operator Meta-Alignment ==="));
    expect(idx("[Coherence-Alignment]")).toBeGreaterThan(idx("[Meta-Alignment Level]"));
    expect(idx("[Synthesis-Alignment]")).toBeGreaterThan(idx("[Coherence-Alignment]"));
    expect(idx("[Stability-Alignment]")).toBeGreaterThan(idx("[Synthesis-Alignment]"));
    expect(idx("[Resilience-Alignment]")).toBeGreaterThan(idx("[Stability-Alignment]"));
    expect(idx("[Immunity-Alignment]")).toBeGreaterThan(idx("[Resilience-Alignment]"));
    expect(idx("[Pattern-Alignment]")).toBeGreaterThan(idx("[Immunity-Alignment]"));
    expect(idx("[Meta-Alignment Trajectory]")).toBeGreaterThan(idx("[Pattern-Alignment]"));
    expect(idx("[Meta-Alignment Drivers]")).toBeGreaterThan(idx("[Meta-Alignment Trajectory]"));
    expect(idx("[Meta-Alignment Inhibitors]")).toBeGreaterThan(idx("[Meta-Alignment Drivers]"));
    expect(idx("[Meta-Alignment Risks]")).toBeGreaterThan(idx("[Meta-Alignment Inhibitors]"));
    expect(idx("[Meta-Alignment Reinforcement]")).toBeGreaterThan(idx("[Meta-Alignment Risks]"));
    expect(idx("[Meta-Alignment Decay]")).toBeGreaterThan(idx("[Meta-Alignment Reinforcement]"));
    expect(idx("[Operator Meta-Alignment Summary]")).toBeGreaterThan(idx("[Meta-Alignment Decay]"));

    // All-optimal baseline — every aligned facet reads strong.
    expect(out).toContain("[Meta-Alignment Level]\nHIGH");
    expect(out).toContain("[Coherence-Alignment]\nstrong alignment");
    expect(out).toContain("[Synthesis-Alignment]\nstrong alignment");
    expect(out).toContain("[Stability-Alignment]\nstrong alignment");
    expect(out).toContain("[Resilience-Alignment]\nstrong alignment");
    expect(out).toContain("[Immunity-Alignment]\nstrong alignment");
    expect(out).toContain("[Pattern-Alignment]\nstable pattern alignment");
    expect(out).toContain("[Meta-Alignment Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("- strong synthesis alignment");
    expect(out).toContain("- strong resilience alignment");
    expect(out).toContain("- stable pattern alignment");
    expect(out).toContain("[Meta-Alignment Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Alignment Risks]\n(none)");
    expect(out).toContain("[Meta-Alignment Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-alignment is steady, with strong synthesis- and resilience-alignment.",
    );
    expect(out).not.toContain("Immunity-alignment remains");
  });

  it("strong synthesis-alignment scenario: synthesis level MEDIUM-HIGH → 'strong alignment' + driver", () => {
    const out = craft({ synthesis: "MEDIUM-HIGH" });

    expect(out).toContain("[Synthesis-Alignment]\nstrong alignment");
    expect(out).toContain("- strong synthesis alignment");
  });

  it("weak immunity-alignment scenario: meta-immunity level LOW → 'weak alignment' + inhibitor + reinforcement", () => {
    const out = craft({ metaImmunity: "LOW" });

    expect(out).toContain("[Immunity-Alignment]\nweak alignment");
    expect(out).toContain("- weak immunity alignment");
    expect(out).toContain("- strengthen immunity alignment");
  });

  it("stable pattern-alignment scenario: meta-pattern level MEDIUM → 'stable pattern alignment' + driver", () => {
    const out = craft({ metaPattern: "MEDIUM" });

    expect(out).toContain("[Pattern-Alignment]\nstable pattern alignment");
    expect(out).toContain("- stable pattern alignment");
  });

  it("summary correctness: improving + strong synthesis/resilience + weak immunity mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-alignment is strengthening, with strong
    //    synthesis- and resilience-alignment. Immunity-alignment remains
    //    weak and may disrupt overall alignment."
    const out = craft({
      direction:      "improving",
      synthesis:      "HIGH",
      metaResilience: "HIGH",
      metaImmunity:   "LOW",
    });

    expect(out).toContain(
      "Operator meta-alignment is strengthening, with strong synthesis- and resilience-alignment. Immunity-alignment remains weak and may disrupt overall alignment.",
    );
  });
});
