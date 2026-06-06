// Card 80 — Operator Meta-Immunity engine unit tests.
//
// Builds the full operator + integration + meta-pattern + meta-
// stability + meta-resilience chain via the canonical helpers so tests
// stay tied to actual upstream outputs. Tests cover the five spec
// scenarios: baseline, weak pressure-immunity, strong clarity-immunity,
// partial load-immunity, and summary correctness.

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
  const metaResilience = buildOperatorMetaResilience(
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability,
  );
  return {
    currState, diff, stability, resilience, immunity, coherence, synthesis,
    integration, metaPattern, metaStability, metaResilience,
  };
}

function metaImmunity(c: ReturnType<typeof fullChain>): string {
  return buildOperatorMetaImmunity(
    c.currState, c.diff, c.stability, c.resilience, c.immunity,
    c.coherence, c.synthesis, c.integration, c.metaPattern, c.metaStability, c.metaResilience,
  );
}

describe("Card 80 — buildOperatorMetaImmunity", () => {
  it("baseline (empty inputs + HIGH system) emits HIGH meta-immunity + all-strong immunities + steady summary", () => {
    const out = metaImmunity(fullChain("", ""));

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Immunity ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Immunity Level]")).toBeGreaterThan(idx("=== Operator Meta-Immunity ==="));
    expect(idx("[Clarity-Immunity]")).toBeGreaterThan(idx("[Meta-Immunity Level]"));
    expect(idx("[Drift-Immunity]")).toBeGreaterThan(idx("[Clarity-Immunity]"));
    expect(idx("[Load-Immunity]")).toBeGreaterThan(idx("[Drift-Immunity]"));
    expect(idx("[Pressure-Immunity]")).toBeGreaterThan(idx("[Load-Immunity]"));
    expect(idx("[Volatility-Immunity]")).toBeGreaterThan(idx("[Pressure-Immunity]"));
    expect(idx("[Meta-Immunity Trajectory]")).toBeGreaterThan(idx("[Volatility-Immunity]"));
    expect(idx("[Meta-Immunity Drivers]")).toBeGreaterThan(idx("[Meta-Immunity Trajectory]"));
    expect(idx("[Meta-Immunity Inhibitors]")).toBeGreaterThan(idx("[Meta-Immunity Drivers]"));
    expect(idx("[Meta-Immunity Risks]")).toBeGreaterThan(idx("[Meta-Immunity Inhibitors]"));
    expect(idx("[Meta-Immunity Reinforcement]")).toBeGreaterThan(idx("[Meta-Immunity Risks]"));
    expect(idx("[Meta-Immunity Decay]")).toBeGreaterThan(idx("[Meta-Immunity Reinforcement]"));
    expect(idx("[Operator Meta-Immunity Summary]")).toBeGreaterThan(idx("[Meta-Immunity Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Meta-Immunity Level]\nHIGH");
    expect(out).toContain("[Clarity-Immunity]\nstrong immunity");
    expect(out).toContain("[Drift-Immunity]\nstrong immunity");
    expect(out).toContain("[Load-Immunity]\nstrong immunity");
    expect(out).toContain("[Pressure-Immunity]\nstrong immunity");
    expect(out).toContain("[Volatility-Immunity]\nstrong immunity");
    expect(out).toContain("[Meta-Immunity Trajectory]\nhigh → high → high (stable)");
    // Steady-state drivers fire; the failure-mode lists stay empty.
    expect(out).toContain("- strong clarity immunity");
    expect(out).toContain("- strong drift immunity");
    expect(out).toContain("- stable meta-pattern");
    expect(out).toContain("[Meta-Immunity Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Immunity Risks]\n(none)");
    expect(out).toContain("[Meta-Immunity Decay]\n(none)");
    expect(out).toContain(
      "Operator meta-immunity is steady, with strong clarity- and drift-immunity.",
    );
    expect(out).not.toContain("Pressure-immunity remains weak");
  });

  it("weak pressure-immunity scenario: pressure=high → 'weak immunity' + pressure inhibitor/risk/reinforcement/decay + summary tail", () => {
    const out = metaImmunity(fullChain("", "pressure=high"));

    expect(out).toContain("[Pressure-Immunity]\nweak immunity");
    expect(out).toContain("- weak pressure immunity");
    expect(out).toContain("- pressure-induced degradation");
    expect(out).toContain("- strengthen pressure immunity");
    expect(out).toContain("- pressure may disrupt immunity");
    expect(out).toContain("Pressure-immunity remains weak and may disrupt overall immunity.");
  });

  it("strong clarity-immunity scenario: clarity=strong (default) → 'strong immunity' + 'strong clarity immunity' driver", () => {
    // pressure=moderate perturbs another dimension while clarity stays
    // strong, so clarity-immunity remains independently strong.
    const out = metaImmunity(fullChain("", "pressure=moderate"));

    expect(out).toContain("[Clarity-Immunity]\nstrong immunity");
    expect(out).toContain("- strong clarity immunity");
    // Pressure at moderate reads as moderate (not weak) immunity.
    expect(out).toContain("[Pressure-Immunity]\nmoderate immunity");
  });

  it("partial load-immunity scenario: load=moderate → 'partial immunity' + load inhibitor/risk/reinforcement", () => {
    const out = metaImmunity(fullChain("", "load=moderate"));

    expect(out).toContain("[Load-Immunity]\npartial immunity");
    expect(out).toContain("- partial load immunity");
    expect(out).toContain("- load imbalance");
    expect(out).toContain("- balance load");
  });

  it("summary correctness: improving + strong clarity/drift + weak pressure mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-immunity is strengthening, with strong clarity-
    //    and drift-immunity. Pressure-immunity remains weak and may
    //    disrupt overall immunity."
    // Engineer prev worse than curr so direction registers as improving
    // (→ "strengthening"), with pressure=elevated driving pressure-
    // immunity to weak while clarity + drift stay strong.
    const prevInput = "clarity=weak load=high";
    const currInput = "pressure=elevated direction=improving";
    const out = metaImmunity(fullChain(prevInput, currInput));

    expect(out).toContain(
      "Operator meta-immunity is strengthening, with strong clarity- and drift-immunity. Pressure-immunity remains weak and may disrupt overall immunity.",
    );
  });
});
