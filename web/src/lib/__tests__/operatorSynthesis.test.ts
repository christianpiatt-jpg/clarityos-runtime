// Card 75 — Operator Synthesis engine unit tests.
//
// Builds operator state/diff/stability/resilience/immunity/coherence
// via the canonical helpers so test fixtures stay tied to actual
// upstream outputs. Tests cover the five spec scenarios: baseline
// synthesis, strong clarity-synthesis, weak pressure-synthesis,
// partial unification, and summary correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }      from "../operatorState";
import { buildOperatorDiff }       from "../operatorStateDiff";
import { buildOperatorStability }  from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";
import { buildOperatorImmunity }   from "../operatorImmunity";
import { buildOperatorCoherence }  from "../operatorCoherence";
import { buildOperatorSynthesis }  from "../operatorSynthesis";

function chain(prevInput: string, currInput: string) {
  const prevState  = buildOperatorState(prevInput);
  const currState  = buildOperatorState(currInput);
  const diff       = buildOperatorDiff(prevState, currState);
  const stability  = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  const immunity   = buildOperatorImmunity(currState, diff, stability, resilience);
  const coherence  = buildOperatorCoherence(currState, diff, stability, resilience, immunity);
  return { currState, diff, stability, resilience, immunity, coherence };
}

describe("Card 75 — buildOperatorSynthesis", () => {
  it("baseline (empty inputs) emits HIGH synthesis + strong integration + steady summary", () => {
    const { currState, diff, stability, resilience, immunity, coherence } = chain("", "");
    const out = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Synthesis ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Synthesis Level]")).toBeGreaterThan(idx("=== Operator Synthesis ==="));
    expect(idx("[Operator Integration]")).toBeGreaterThan(idx("[Synthesis Level]"));
    expect(idx("[Operator Unification]")).toBeGreaterThan(idx("[Operator Integration]"));
    expect(idx("[Clarity-Synthesis]")).toBeGreaterThan(idx("[Operator Unification]"));
    expect(idx("[Drift-Synthesis]")).toBeGreaterThan(idx("[Clarity-Synthesis]"));
    expect(idx("[Load-Synthesis]")).toBeGreaterThan(idx("[Drift-Synthesis]"));
    expect(idx("[Pressure-Synthesis]")).toBeGreaterThan(idx("[Load-Synthesis]"));
    expect(idx("[Synthesis Trajectory]")).toBeGreaterThan(idx("[Pressure-Synthesis]"));
    expect(idx("[Synthesis Drivers]")).toBeGreaterThan(idx("[Synthesis Trajectory]"));
    expect(idx("[Synthesis Inhibitors]")).toBeGreaterThan(idx("[Synthesis Drivers]"));
    expect(idx("[Synthesis Risks]")).toBeGreaterThan(idx("[Synthesis Inhibitors]"));
    expect(idx("[Synthesis Reinforcement]")).toBeGreaterThan(idx("[Synthesis Risks]"));
    expect(idx("[Synthesis Decay]")).toBeGreaterThan(idx("[Synthesis Reinforcement]"));
    expect(idx("[Operator Synthesis Summary]")).toBeGreaterThan(idx("[Synthesis Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Synthesis Level]\nHIGH");
    expect(out).toContain("[Operator Integration]\nstrong integration");
    expect(out).toContain("[Operator Unification]\nstrong unification");
    expect(out).toContain("[Clarity-Synthesis]\nstrong");
    expect(out).toContain("[Drift-Synthesis]\nstable");
    expect(out).toContain("[Load-Synthesis]\nstrong");
    expect(out).toContain("[Pressure-Synthesis]\nstrong");
    expect(out).toContain("[Synthesis Trajectory]\nhigh → high → high (stable)");
    // Drivers fire even at baseline (strong clarity + stable drift +
    // steady integration are forward-supporting signals).
    expect(out).toContain("- strong clarity synthesis");
    expect(out).toContain("- stable drift synthesis");
    expect(out).toContain("[Synthesis Inhibitors]\n(none)");
    expect(out).toContain("[Synthesis Risks]\n(none)");
    expect(out).toContain("[Synthesis Decay]\n(none)");
    expect(out).toContain("Operator synthesis is steady, with strong clarity-synthesis and stable drift-synthesis.");
    // No pressure-disruption tail when baseline.
    expect(out).not.toContain("Pressure-synthesis remains weak");
  });

  it("strong clarity-synthesis scenario: clarity=strong (default) reports strong clarity-synthesis", () => {
    const { currState, diff, stability, resilience, immunity, coherence } = chain("", "load=moderate");
    const out = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);

    expect(out).toContain("[Clarity-Synthesis]\nstrong");
    // load=moderate → load-synthesis=moderate.
    expect(out).toContain("[Load-Synthesis]\nmoderate");
    // Strong clarity drives the "strong clarity synthesis" line.
    expect(out).toContain("- strong clarity synthesis");
  });

  it("weak pressure-synthesis scenario: pressure=high reports weak pressure-synthesis + summary mentions disruption", () => {
    const { currState, diff, stability, resilience, immunity, coherence } = chain("", "pressure=high");
    const out = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);

    expect(out).toContain("[Pressure-Synthesis]\nweak");
    // Inhibitor + risk fire for non-low pressure.
    expect(out).toContain("- weak pressure synthesis");
    expect(out).toContain("- fragmentation under pressure");
    // Summary appends the pressure-disruption clause.
    expect(out).toContain("Pressure-synthesis remains weak and may disrupt overall synthesis.");
  });

  it("partial unification scenario: pressure=high → upstream layers spread, coherence falls behind → partial unification", () => {
    const { currState, diff, stability, resilience, immunity, coherence } = chain("", "pressure=high");
    const out = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);

    // pressure=high pushes stability/resilience/immunity into the
    // MEDIUM band while coherence's average lags one step behind →
    // the spread-by-1 case yields partial unification.
    expect(out).toContain("[Operator Unification]\npartial unification");
    expect(out).toContain("- partial unification");
    // Reinforcement uses "strengthen unification" when non-strong.
    expect(out).toContain("- strengthen unification");
  });

  it("summary correctness: improving + strong clarity + stable drift + weak pressure mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator synthesis is strengthening, with strong clarity-
    //    synthesis and stable drift-synthesis. Pressure-synthesis
    //    remains weak and may disrupt overall synthesis."
    const prevInput = "clarity=weak stability=weak load=high drift=high";
    const currInput = "clarity=strong pressure=elevated direction=improving";
    const { currState, diff, stability, resilience, immunity, coherence } = chain(prevInput, currInput);
    const out = buildOperatorSynthesis(currState, diff, stability, resilience, immunity, coherence);

    expect(out).toContain("[Clarity-Synthesis]\nstrong");
    expect(out).toContain("[Drift-Synthesis]\nstable");
    expect(out).toContain("[Pressure-Synthesis]\nweak");
    expect(out).toContain(
      "Operator synthesis is strengthening, with strong clarity-synthesis and stable drift-synthesis. Pressure-synthesis remains weak and may disrupt overall synthesis.",
    );
  });
});
