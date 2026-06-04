// Card 77 — Operator Meta-Pattern engine unit tests.
//
// Builds the full operator + integration chain via the canonical
// helpers so tests stay tied to actual upstream outputs. Tests
// cover the five spec scenarios: baseline, elevated pressure,
// partial alignment, stable drift, and summary correctness.

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
  return { currState, diff, stability, resilience, immunity, coherence, synthesis, integration };
}

describe("Card 77 — buildOperatorMetaPattern", () => {
  it("baseline (empty inputs + HIGH system) emits HIGH meta-pattern + strong alignment + steady summary", () => {
    const c = fullChain("", "");
    const out = buildOperatorMetaPattern(
      c.currState, c.diff, c.stability, c.resilience, c.immunity,
      c.coherence, c.synthesis, c.integration,
    );

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Meta-Pattern ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Meta-Pattern Level]")).toBeGreaterThan(idx("=== Operator Meta-Pattern ==="));
    expect(idx("[Meta-Alignment]")).toBeGreaterThan(idx("[Meta-Pattern Level]"));
    expect(idx("[Meta-Drift Detection]")).toBeGreaterThan(idx("[Meta-Alignment]"));
    expect(idx("[Meta-Load Interpretation]")).toBeGreaterThan(idx("[Meta-Drift Detection]"));
    expect(idx("[Meta-Pressure Interpretation]")).toBeGreaterThan(idx("[Meta-Load Interpretation]"));
    expect(idx("[Meta-Trajectory]")).toBeGreaterThan(idx("[Meta-Pressure Interpretation]"));
    expect(idx("[Meta-Pattern Drivers]")).toBeGreaterThan(idx("[Meta-Trajectory]"));
    expect(idx("[Meta-Pattern Inhibitors]")).toBeGreaterThan(idx("[Meta-Pattern Drivers]"));
    expect(idx("[Meta-Pattern Risks]")).toBeGreaterThan(idx("[Meta-Pattern Inhibitors]"));
    expect(idx("[Meta-Pattern Reinforcement]")).toBeGreaterThan(idx("[Meta-Pattern Risks]"));
    expect(idx("[Meta-Pattern Decay]")).toBeGreaterThan(idx("[Meta-Pattern Reinforcement]"));
    expect(idx("[Operator Meta-Pattern Summary]")).toBeGreaterThan(idx("[Meta-Pattern Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Meta-Pattern Level]\nHIGH");
    expect(out).toContain("[Meta-Alignment]\nstrong alignment");
    expect(out).toContain("[Meta-Drift Detection]\nlow drift detected");
    expect(out).toContain("[Meta-Load Interpretation]\nlow load");
    expect(out).toContain("[Meta-Pressure Interpretation]\nlow pressure");
    expect(out).toContain("[Meta-Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Meta-Pattern Inhibitors]\n(none)");
    expect(out).toContain("[Meta-Pattern Risks]\n(none)");
    expect(out).toContain("[Meta-Pattern Decay]\n(none)");
    expect(out).toContain("Operator meta-pattern stability is steady, with strong synthesis and stable drift.");
    expect(out).not.toContain("Pressure remains elevated");
  });

  it("elevated pressure scenario: pressure=elevated → 'elevated pressure' interpretation + summary tail", () => {
    const c = fullChain("", "pressure=elevated");
    const out = buildOperatorMetaPattern(
      c.currState, c.diff, c.stability, c.resilience, c.immunity,
      c.coherence, c.synthesis, c.integration,
    );

    expect(out).toContain("[Meta-Pressure Interpretation]\nelevated pressure");
    expect(out).toContain("- elevated pressure");
    expect(out).toContain("Pressure remains elevated and may disrupt overall pattern integrity.");
    // Pattern-fragmentation + pressure-induced-drift risks fire too.
    expect(out).toContain("- pattern fragmentation");
    expect(out).toContain("- pressure-induced drift");
  });

  it("partial alignment scenario: system MEDIUM-HIGH vs operator HIGH → partial alignment registers", () => {
    const c = fullChain("", "", "MEDIUM-HIGH");
    const out = buildOperatorMetaPattern(
      c.currState, c.diff, c.stability, c.resilience, c.immunity,
      c.coherence, c.synthesis, c.integration,
    );

    expect(out).toContain("[Meta-Alignment]\npartial alignment");
    expect(out).toContain("- partial alignment");
    expect(out).toContain("- strengthen alignment");
  });

  it("stable drift scenario: drift=low (default) registers as 'low drift detected' + 'stable drift profile' driver", () => {
    const c = fullChain("", "");
    const out = buildOperatorMetaPattern(
      c.currState, c.diff, c.stability, c.resilience, c.immunity,
      c.coherence, c.synthesis, c.integration,
    );

    expect(out).toContain("[Meta-Drift Detection]\nlow drift detected");
    expect(out).toContain("- stable drift profile");
  });

  it("summary correctness: improving + strong synthesis + stable drift + elevated pressure mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator meta-pattern stability is improving, with strong
    //    synthesis and stable drift. Pressure remains elevated and
    //    may disrupt overall pattern integrity."
    // Engineer prev/curr so direction registers as improving while
    // synthesis stays at strong (chain at MEDIUM-HIGH). Pressure=
    // elevated alone keeps the chain at MEDIUM-HIGH (score -2);
    // adding clarity=partial would drop it further so we leave
    // clarity at the default strong.
    const prevInput = "clarity=weak load=high";
    const currInput = "pressure=elevated direction=improving";
    const c = fullChain(prevInput, currInput);
    const out = buildOperatorMetaPattern(
      c.currState, c.diff, c.stability, c.resilience, c.immunity,
      c.coherence, c.synthesis, c.integration,
    );

    expect(out).toContain(
      "Operator meta-pattern stability is improving, with strong synthesis and stable drift. Pressure remains elevated and may disrupt overall pattern integrity.",
    );
  });
});
