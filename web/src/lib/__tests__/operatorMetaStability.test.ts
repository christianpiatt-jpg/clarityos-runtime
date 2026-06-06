// Card 78 — Operator Meta-Stability engine unit tests.
//
// Builds the full operator + integration + meta-pattern chain via the
// canonical helpers so tests stay tied to actual upstream outputs.
// Tests cover the five spec scenarios: baseline, weak pressure-
// stability, strong drift-stability, partial load-stability, and
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
  return { currState, diff, stability, resilience, immunity, coherence, synthesis, integration, metaPattern };
}

function metaStability(c: ReturnType<typeof fullChain>): string {
  return buildOperatorMetaStability(
    c.currState, c.diff, c.stability, c.resilience, c.immunity,
    c.coherence, c.synthesis, c.integration, c.metaPattern,
  );
}

describe("Card 78 — buildOperatorMetaStability", () => {
  it("baseline (empty inputs + HIGH system) emits HIGH meta-stability + all-strong stabilities + steady summary", () => {
    const out = metaStability(fullChain("", ""));

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Stability ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Stability Level]")).toBeGreaterThan(idx("=== Operator Meta-Stability ==="));
    expect(idx("[Transition-Stability]")).toBeGreaterThan(idx("[Meta-Stability Level]"));
    expect(idx("[Load-Stability]")).toBeGreaterThan(idx("[Transition-Stability]"));
    expect(idx("[Pressure-Stability]")).toBeGreaterThan(idx("[Load-Stability]"));
    expect(idx("[Drift-Stability]")).toBeGreaterThan(idx("[Pressure-Stability]"));
    expect(idx("[Meta-Stability Trajectory]")).toBeGreaterThan(idx("[Drift-Stability]"));
    expect(idx("[Meta-Stability Drivers]")).toBeGreaterThan(idx("[Meta-Stability Trajectory]"));
    expect(idx("[Meta-Stability Inhibitors]")).toBeGreaterThan(idx("[Meta-Stability Drivers]"));
    expect(idx("[Meta-Stability Risks]")).toBeGreaterThan(idx("[Meta-Stability Inhibitors]"));
    expect(idx("[Meta-Stability Reinforcement]")).toBeGreaterThan(idx("[Meta-Stability Risks]"));
    expect(idx("[Meta-Stability Decay]")).toBeGreaterThan(idx("[Meta-Stability Reinforcement]"));
    expect(idx("[Operator Meta-Stability Summary]")).toBeGreaterThan(idx("[Meta-Stability Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Meta-Stability Level]\nHIGH");
    expect(out).toContain("[Transition-Stability]\nstrong stability");
    expect(out).toContain("[Load-Stability]\nstrong stability");
    expect(out).toContain("[Pressure-Stability]\nstrong stability");
    expect(out).toContain("[Drift-Stability]\nstrong stability");
    expect(out).toContain("[Meta-Stability Trajectory]\nhigh → high → high (stable)");
    // Steady-state drivers fire; the failure-mode lists stay empty.
    expect(out).toContain("- strong drift stability");
    expect(out).toContain("- stable synthesis");
    expect(out).toContain("- stable meta-pattern");
    expect(out).toContain("[Meta-Stability Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Stability Risks]\n(none)");
    expect(out).toContain("[Meta-Stability Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-stability is steady, with strong drift-stability and stable meta-pattern.",
    );
    expect(out).not.toContain("Pressure-stability remains weak");
  });

  it("weak pressure-stability scenario: pressure=high → 'weak stability' + pressure inhibitor/risk/reinforcement/decay + summary tail", () => {
    const out = metaStability(fullChain("", "pressure=high"));

    expect(out).toContain("[Pressure-Stability]\nweak stability");
    expect(out).toContain("- weak pressure stability");
    expect(out).toContain("- pressure-induced instability");
    expect(out).toContain("- strengthen pressure stability");
    expect(out).toContain("- pressure may disrupt stability");
    expect(out).toContain("Pressure-stability remains weak and may disrupt overall stability.");
  });

  it("strong drift-stability scenario: drift=low (default) → 'strong stability' + 'strong drift stability' driver", () => {
    // pressure=moderate keeps drift independently low so drift-stability
    // stays strong while another dimension is perturbed.
    const out = metaStability(fullChain("", "pressure=moderate"));

    expect(out).toContain("[Drift-Stability]\nstrong stability");
    expect(out).toContain("- strong drift stability");
    // Maintain (not strengthen) drift control while drift is strong.
    expect(out).toContain("- maintain drift control");
    // Pressure at moderate reads as moderate (not weak) stability.
    expect(out).toContain("[Pressure-Stability]\nmoderate stability");
  });

  it("partial load-stability scenario: load=moderate → 'partial stability' + load inhibitor/risk/reinforcement", () => {
    const out = metaStability(fullChain("", "load=moderate"));

    expect(out).toContain("[Load-Stability]\npartial stability");
    expect(out).toContain("- partial load stability");
    expect(out).toContain("- load imbalance");
    expect(out).toContain("- balance load");
  });

  it("summary correctness: improving + strong drift + stable meta-pattern + weak pressure mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-stability is improving, with strong drift-
    //    stability and stable meta-pattern. Pressure-stability remains
    //    weak and may disrupt overall stability."
    // Engineer prev worse than curr so direction registers as improving,
    // with pressure=elevated driving pressure-stability to weak while
    // drift stays low (strong) and the meta-pattern holds (stable).
    const prevInput = "clarity=weak load=high";
    const currInput = "pressure=elevated direction=improving";
    const out = metaStability(fullChain(prevInput, currInput));

    expect(out).toContain(
      "Operator meta-stability is improving, with strong drift-stability and stable meta-pattern. Pressure-stability remains weak and may disrupt overall stability.",
    );
  });
});
