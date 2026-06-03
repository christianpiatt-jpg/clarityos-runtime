// Card 79 — Operator Meta-Resilience engine unit tests.
//
// Builds the full operator + integration + meta-pattern + meta-
// stability chain via the canonical helpers so tests stay tied to
// actual upstream outputs. Tests cover the five spec scenarios:
// baseline, weak pressure-resilience, strong drift-resilience, partial
// load-resilience, and summary correctness.

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

function sysImmunity(score: string): string {
  return `=== Structural Immunity ===\n\n[Immunity Score]\n${score}\n`;
}
function sysResilience(score: string): string {
  return `=== Structural Resilience ===\n\n[Resilience Score]\n${score}\n`;
}
function sysStability(prob: string): string {
  return `=== Structural Stabilization ===\n\n[Stabilization Probability]\n${prob}\n`;
}

function fullChain(
  prevInput: string,
  currInput: string,
  systemScore: string = "HIGH",
) {
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
  return {
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability,
  };
}

function metaResilience(c: ReturnType<typeof fullChain>): string {
  return buildOperatorMetaResilience(
    c.currState, c.diff, c.stability, c.resilience, c.immunity,
    c.coherence, c.synthesis, c.integration, c.metaPattern, c.metaStability,
  );
}

describe("Card 79 — buildOperatorMetaResilience", () => {
  it("baseline (empty inputs + HIGH system) emits HIGH meta-resilience + all-strong resiliences + steady summary", () => {
    const out = metaResilience(fullChain("", ""));

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Resilience ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Resilience Level]")).toBeGreaterThan(idx("=== Operator Meta-Resilience ==="));
    expect(idx("[Volatility-Resilience]")).toBeGreaterThan(idx("[Meta-Resilience Level]"));
    expect(idx("[Pressure-Resilience]")).toBeGreaterThan(idx("[Volatility-Resilience]"));
    expect(idx("[Drift-Resilience]")).toBeGreaterThan(idx("[Pressure-Resilience]"));
    expect(idx("[Load-Resilience]")).toBeGreaterThan(idx("[Drift-Resilience]"));
    expect(idx("[Meta-Resilience Trajectory]")).toBeGreaterThan(idx("[Load-Resilience]"));
    expect(idx("[Meta-Resilience Drivers]")).toBeGreaterThan(idx("[Meta-Resilience Trajectory]"));
    expect(idx("[Meta-Resilience Inhibitors]")).toBeGreaterThan(idx("[Meta-Resilience Drivers]"));
    expect(idx("[Meta-Resilience Risks]")).toBeGreaterThan(idx("[Meta-Resilience Inhibitors]"));
    expect(idx("[Meta-Resilience Reinforcement]")).toBeGreaterThan(idx("[Meta-Resilience Risks]"));
    expect(idx("[Meta-Resilience Decay]")).toBeGreaterThan(idx("[Meta-Resilience Reinforcement]"));
    expect(idx("[Operator Meta-Resilience Summary]")).toBeGreaterThan(idx("[Meta-Resilience Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Meta-Resilience Level]\nHIGH");
    expect(out).toContain("[Volatility-Resilience]\nstrong resilience");
    expect(out).toContain("[Pressure-Resilience]\nstrong resilience");
    expect(out).toContain("[Drift-Resilience]\nstrong resilience");
    expect(out).toContain("[Load-Resilience]\nstrong resilience");
    expect(out).toContain("[Meta-Resilience Trajectory]\nhigh → high → high (stable)");
    // Steady-state drivers fire; the failure-mode lists stay empty.
    expect(out).toContain("- strong drift resilience");
    expect(out).toContain("- stable synthesis");
    expect(out).toContain("- stable meta-pattern");
    expect(out).toContain("[Meta-Resilience Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Resilience Risks]\n(none)");
    expect(out).toContain("[Meta-Resilience Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-resilience is steady, with strong drift-resilience and stable meta-pattern.",
    );
    expect(out).not.toContain("Pressure-resilience remains weak");
  });

  it("weak pressure-resilience scenario: pressure=high → 'weak resilience' + pressure inhibitor/risk/reinforcement/decay + summary tail", () => {
    const out = metaResilience(fullChain("", "pressure=high"));

    expect(out).toContain("[Pressure-Resilience]\nweak resilience");
    expect(out).toContain("- weak pressure resilience");
    expect(out).toContain("- pressure-induced degradation");
    expect(out).toContain("- strengthen pressure resilience");
    expect(out).toContain("- pressure may disrupt resilience");
    expect(out).toContain("Pressure-resilience remains weak and may disrupt overall resilience.");
  });

  it("strong drift-resilience scenario: drift=low (default) → 'strong resilience' + 'strong drift resilience' driver", () => {
    // pressure=moderate keeps drift independently low so drift-
    // resilience stays strong while another dimension is perturbed.
    const out = metaResilience(fullChain("", "pressure=moderate"));

    expect(out).toContain("[Drift-Resilience]\nstrong resilience");
    expect(out).toContain("- strong drift resilience");
    // Maintain (not strengthen) drift control while drift is strong.
    expect(out).toContain("- maintain drift control");
    // Pressure at moderate reads as moderate (not weak) resilience.
    expect(out).toContain("[Pressure-Resilience]\nmoderate resilience");
  });

  it("partial load-resilience scenario: load=moderate → 'partial resilience' + load inhibitor/risk/reinforcement", () => {
    const out = metaResilience(fullChain("", "load=moderate"));

    expect(out).toContain("[Load-Resilience]\npartial resilience");
    expect(out).toContain("- partial load resilience");
    expect(out).toContain("- load imbalance");
    expect(out).toContain("- balance load");
  });

  it("summary correctness: improving + strong drift + stable meta-pattern + weak pressure mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-resilience is strengthening, with strong drift-
    //    resilience and stable meta-pattern. Pressure-resilience remains
    //    weak and may disrupt overall resilience."
    // Engineer prev worse than curr so direction registers as improving
    // (→ "strengthening"), with pressure=elevated driving pressure-
    // resilience to weak while drift stays low (strong) and the meta-
    // pattern holds (stable).
    const prevInput = "clarity=weak load=high";
    const currInput = "pressure=elevated direction=improving";
    const out = metaResilience(fullChain(prevInput, currInput));

    expect(out).toContain(
      "Operator meta-resilience is strengthening, with strong drift-resilience and stable meta-pattern. Pressure-resilience remains weak and may disrupt overall resilience.",
    );
  });
});
