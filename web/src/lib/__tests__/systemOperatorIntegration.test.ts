// Card 76 — System-Operator Integration engine unit tests.
//
// Builds the operator chain via the canonical helpers and pairs it
// with synthetic system-side inputs (Phase-3 score-bearing text
// blocks). Tests cover the five spec scenarios: baseline, strong
// synthesis, partial alignment, pressure sensitivity, and summary
// correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }      from "../operatorState";
import { buildOperatorDiff }       from "../operatorStateDiff";
import { buildOperatorStability }  from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";
import { buildOperatorImmunity }   from "../operatorImmunity";
import { buildOperatorCoherence }  from "../operatorCoherence";
import { buildOperatorSynthesis }  from "../operatorSynthesis";
import { buildSystemOperatorIntegration } from "../systemOperatorIntegration";

function opChain(prevInput: string, currInput: string) {
  const prevState  = buildOperatorState(prevInput);
  const currState  = buildOperatorState(currInput);
  const diff       = buildOperatorDiff(prevState, currState);
  const stability  = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  const immunity   = buildOperatorImmunity(currState, diff, stability, resilience);
  const coherence  = buildOperatorCoherence(currState, diff, stability, resilience, immunity);
  const synthesis  = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);
  return { currState, diff, stability, resilience, immunity, coherence, synthesis };
}

// Synthetic system-side text fixtures. Phase-3 Cards 58/59/60 emit
// `[Stabilization Probability]`, `[Resilience Score]`, `[Immunity
// Score]` blocks respectively. We only construct what the Card 76
// helper actually parses — everything else is omitted.
function sysStability(prob: string): string {
  return `=== Structural Stabilization ===\n\n[Stabilization Probability]\n${prob}\n`;
}
function sysResilience(score: string): string {
  return `=== Structural Resilience ===\n\n[Resilience Score]\n${score}\n`;
}
function sysImmunity(score: string): string {
  return `=== Structural Immunity ===\n\n[Immunity Score]\n${score}\n`;
}

describe("Card 76 — buildSystemOperatorIntegration", () => {
  it("baseline (empty inputs + HIGH system scores) emits HIGH integration + strong alignment + steady summary", () => {
    const op = opChain("", "");
    const out = buildSystemOperatorIntegration(
      "", "",
      sysStability("HIGH"), sysResilience("HIGH"), sysImmunity("HIGH"),
      op.currState, op.diff, op.stability, op.resilience, op.immunity, op.coherence, op.synthesis,
    );

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== System-Operator Integration ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Integration Level]")).toBeGreaterThan(idx("=== System-Operator Integration ==="));
    expect(idx("[System-Operator Alignment]")).toBeGreaterThan(idx("[Integration Level]"));
    expect(idx("[System-Operator Coherence]")).toBeGreaterThan(idx("[System-Operator Alignment]"));
    expect(idx("[System-Operator Synthesis]")).toBeGreaterThan(idx("[System-Operator Coherence]"));
    expect(idx("[Integration Trajectory]")).toBeGreaterThan(idx("[System-Operator Synthesis]"));
    expect(idx("[Integration Drivers]")).toBeGreaterThan(idx("[Integration Trajectory]"));
    expect(idx("[Integration Inhibitors]")).toBeGreaterThan(idx("[Integration Drivers]"));
    expect(idx("[Integration Risks]")).toBeGreaterThan(idx("[Integration Inhibitors]"));
    expect(idx("[Integration Reinforcement]")).toBeGreaterThan(idx("[Integration Risks]"));
    expect(idx("[Integration Decay]")).toBeGreaterThan(idx("[Integration Reinforcement]"));
    expect(idx("[System-Operator Integration Summary]")).toBeGreaterThan(idx("[Integration Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Integration Level]\nHIGH");
    expect(out).toContain("[System-Operator Alignment]\nstrong alignment");
    expect(out).toContain("[System-Operator Coherence]\nstrong coherence");
    expect(out).toContain("[System-Operator Synthesis]\nstrong synthesis");
    expect(out).toContain("[Integration Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Integration Inhibitors]\n(none)");
    expect(out).toContain("[Integration Risks]\n(none)");
    expect(out).toContain("[Integration Decay]\n(none)");
    expect(out).toContain("System-operator integration is steady, with strong synthesis and strong coherence.");
    // No alignment-disruption tail when baseline.
    expect(out).not.toContain("Alignment remains partial");
  });

  it("strong synthesis scenario: operator chain at HIGH → strong synthesis driver fires", () => {
    const op = opChain("", "");
    const out = buildSystemOperatorIntegration(
      "", "",
      sysStability("HIGH"), sysResilience("HIGH"), sysImmunity("HIGH"),
      op.currState, op.diff, op.stability, op.resilience, op.immunity, op.coherence, op.synthesis,
    );

    expect(out).toContain("[System-Operator Synthesis]\nstrong synthesis");
    expect(out).toContain("- strong operator synthesis");
    expect(out).toContain("- stable system resilience");
  });

  it("partial alignment scenario: system MEDIUM-HIGH but operator HIGH → diff=1 → partial alignment", () => {
    const op = opChain("", "");
    // System scores at MEDIUM-HIGH while operator stack stays at HIGH
    // → alignment diff is 1, neither side is at HIGH+HIGH → partial.
    const out = buildSystemOperatorIntegration(
      "", "",
      sysStability("MEDIUM-HIGH"), sysResilience("MEDIUM-HIGH"), sysImmunity("MEDIUM-HIGH"),
      op.currState, op.diff, op.stability, op.resilience, op.immunity, op.coherence, op.synthesis,
    );

    expect(out).toContain("[System-Operator Alignment]\npartial alignment");
    expect(out).toContain("- partial alignment");
    expect(out).toContain("- misalignment between system and operator");
    // Summary appends the alignment-disruption tail when partial.
    expect(out).toContain("Alignment remains partial and may disrupt overall integration.");
    // Reinforcement uses "strengthen alignment" instead of "maintain".
    expect(out).toContain("- strengthen alignment");
  });

  it("pressure sensitivity scenario: operator pressure=elevated registers as inhibitor + decay risk", () => {
    const op = opChain("", "pressure=elevated");
    const out = buildSystemOperatorIntegration(
      "", "",
      sysStability("HIGH"), sysResilience("HIGH"), sysImmunity("HIGH"),
      op.currState, op.diff, op.stability, op.resilience, op.immunity, op.coherence, op.synthesis,
    );

    expect(out).toContain("- pressure sensitivity");
    expect(out).toContain("- fragmentation under pressure");
    expect(out).toContain("- pressure may disrupt integration");
  });

  it("summary correctness: improving + system MEDIUM-HIGH + operator MEDIUM-HIGH + partial alignment mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "System-operator integration is strengthening, with strong
    //    synthesis and moderate coherence. Alignment remains partial
    //    and may disrupt overall integration."
    // Engineer operator chain so direction registers as improving
    // and the upstream layers land at MEDIUM-HIGH (so coherence
    // reads "moderate" but synthesis still reads "strong").
    const prevInput = "clarity=weak load=high";
    const currInput = "clarity=partial direction=improving";
    const op = opChain(prevInput, currInput);
    const out = buildSystemOperatorIntegration(
      "", "",
      sysStability("MEDIUM-HIGH"), sysResilience("MEDIUM-HIGH"), sysImmunity("MEDIUM-HIGH"),
      op.currState, op.diff, op.stability, op.resilience, op.immunity, op.coherence, op.synthesis,
    );

    // Verify the summary phrasing exactly matches the spec demo.
    expect(out).toContain(
      "System-operator integration is strengthening, with strong synthesis and moderate coherence. Alignment remains partial and may disrupt overall integration.",
    );
  });
});
