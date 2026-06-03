// Card 74 — Operator Coherence engine unit tests.
//
// Builds operator state/diff/stability/resilience/immunity via the
// canonical helpers so test fixtures stay tied to actual upstream
// outputs. Tests cover the five spec scenarios: baseline coherence,
// strong clarity-alignment, weak pressure-alignment, moderate
// integration, and summary correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }      from "../operatorState";
import { buildOperatorDiff }       from "../operatorStateDiff";
import { buildOperatorStability }  from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";
import { buildOperatorImmunity }   from "../operatorImmunity";
import { buildOperatorCoherence }  from "../operatorCoherence";

function chain(prevInput: string, currInput: string) {
  const prevState  = buildOperatorState(prevInput);
  const currState  = buildOperatorState(currInput);
  const diff       = buildOperatorDiff(prevState, currState);
  const stability  = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  const immunity   = buildOperatorImmunity(currState, diff, stability, resilience);
  return { currState, diff, stability, resilience, immunity };
}

describe("Card 74 — buildOperatorCoherence", () => {
  it("baseline (empty inputs) emits HIGH coherence + strong alignment + steady summary", () => {
    const { currState, diff, stability, resilience, immunity } = chain("", "");
    const out = buildOperatorCoherence(currState, diff, stability, resilience, immunity);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Coherence ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Coherence Level]")).toBeGreaterThan(idx("=== Operator Coherence ==="));
    expect(idx("[Operator Alignment]")).toBeGreaterThan(idx("[Coherence Level]"));
    expect(idx("[Operator Integration]")).toBeGreaterThan(idx("[Operator Alignment]"));
    expect(idx("[Clarity-Alignment]")).toBeGreaterThan(idx("[Operator Integration]"));
    expect(idx("[Drift-Alignment]")).toBeGreaterThan(idx("[Clarity-Alignment]"));
    expect(idx("[Load-Alignment]")).toBeGreaterThan(idx("[Drift-Alignment]"));
    expect(idx("[Pressure-Alignment]")).toBeGreaterThan(idx("[Load-Alignment]"));
    expect(idx("[Coherence Trajectory]")).toBeGreaterThan(idx("[Pressure-Alignment]"));
    expect(idx("[Coherence Drivers]")).toBeGreaterThan(idx("[Coherence Trajectory]"));
    expect(idx("[Coherence Inhibitors]")).toBeGreaterThan(idx("[Coherence Drivers]"));
    expect(idx("[Coherence Risks]")).toBeGreaterThan(idx("[Coherence Inhibitors]"));
    expect(idx("[Coherence Reinforcement]")).toBeGreaterThan(idx("[Coherence Risks]"));
    expect(idx("[Coherence Decay]")).toBeGreaterThan(idx("[Coherence Reinforcement]"));
    expect(idx("[Operator Coherence Summary]")).toBeGreaterThan(idx("[Coherence Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Coherence Level]\nHIGH");
    expect(out).toContain("[Operator Alignment]\nstrong alignment");
    expect(out).toContain("[Operator Integration]\nstrong integration");
    expect(out).toContain("[Clarity-Alignment]\nstrong");
    expect(out).toContain("[Drift-Alignment]\nstrong");
    expect(out).toContain("[Load-Alignment]\nstrong");
    expect(out).toContain("[Pressure-Alignment]\nstrong");
    expect(out).toContain("[Coherence Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Coherence Drivers]\n(none)");
    expect(out).toContain("[Coherence Inhibitors]\n(none)");
    expect(out).toContain("[Coherence Risks]\n(none)");
    expect(out).toContain("[Coherence Decay]\n(none)");
    expect(out).toContain("Operator coherence is steady, with strong clarity-alignment and strong integration.");
    // No pressure-alignment-weak tail when baseline.
    expect(out).not.toContain("Pressure-alignment remains weak");
  });

  it("strong clarity-alignment scenario: clarity=strong (default) reports strong clarity-alignment", () => {
    // Use a non-baseline scenario where clarity remains strong but
    // other dims degrade — verifies clarity-alignment still reads
    // "strong" independent of other state.
    const { currState, diff, stability, resilience, immunity } = chain("", "load=moderate");
    const out = buildOperatorCoherence(currState, diff, stability, resilience, immunity);

    expect(out).toContain("[Clarity-Alignment]\nstrong");
    // load=moderate → load-alignment=partial.
    expect(out).toContain("[Load-Alignment]\npartial");
  });

  it("weak pressure-alignment scenario: pressure=high reports weak pressure-alignment + summary mentions disruption", () => {
    const { currState, diff, stability, resilience, immunity } = chain("", "pressure=high");
    const out = buildOperatorCoherence(currState, diff, stability, resilience, immunity);

    expect(out).toContain("[Pressure-Alignment]\nweak");
    // Inhibitor + risk fire for non-low pressure.
    expect(out).toContain("- elevated pressure");
    expect(out).toContain("- misalignment under pressure");
    // Summary appends the pressure-disruption clause.
    expect(out).toContain("Pressure-alignment remains weak and may disrupt overall coherence.");
  });

  it("moderate integration scenario: mixed upstream layer ranks → moderate integration", () => {
    // pressure=high forces upstream layers to MEDIUM-ish ranks, which
    // gives a mixed (not-all-strong, not-all-weak) integration tier.
    const { currState, diff, stability, resilience, immunity } = chain("", "pressure=high");
    const out = buildOperatorCoherence(currState, diff, stability, resilience, immunity);

    expect(out).toContain("[Operator Integration]\nmoderate integration");
  });

  it("summary correctness: improving + strong clarity-alignment + moderate integration + weak pressure-alignment mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator coherence is improving, with strong clarity-
    //    alignment and moderate integration. Pressure-alignment
    //    remains weak and may disrupt overall coherence."
    // Engineer prev/curr so direction registers as improving and
    // upstream layers fall in the MEDIUM-ish band that yields
    // moderate integration.
    const prevInput = "clarity=weak stability=weak load=high drift=high";
    const currInput = "load=moderate drift=moderate clarity=strong pressure=elevated direction=improving";
    const { currState, diff, stability, resilience, immunity } = chain(prevInput, currInput);
    const out = buildOperatorCoherence(currState, diff, stability, resilience, immunity);

    expect(out).toContain("[Clarity-Alignment]\nstrong");
    expect(out).toContain("[Pressure-Alignment]\nweak");
    expect(out).toContain("[Operator Integration]\nmoderate integration");
    expect(out).toContain(
      "Operator coherence is improving, with strong clarity-alignment and moderate integration. Pressure-alignment remains weak and may disrupt overall coherence.",
    );
  });
});
