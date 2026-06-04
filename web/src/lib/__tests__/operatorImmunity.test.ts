// Card 73 — Operator Immunity engine unit tests.
//
// Builds operator state/diff/stability/resilience via the canonical
// helpers so test fixtures stay tied to actual upstream outputs.
// Tests cover the five spec scenarios: baseline immunity, strong
// drift-immunity, weak pressure-immunity, moderate shielding, and
// summary correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }      from "../operatorState";
import { buildOperatorDiff }       from "../operatorStateDiff";
import { buildOperatorStability }  from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";
import { buildOperatorImmunity }   from "../operatorImmunity";

function chain(prevInput: string, currInput: string) {
  const prevState = buildOperatorState(prevInput);
  const currState = buildOperatorState(currInput);
  const diff      = buildOperatorDiff(prevState, currState);
  const stability = buildOperatorStability(currState, diff);
  const resilience = buildOperatorResilience(currState, diff, stability);
  return { currState, diff, stability, resilience };
}

describe("Card 73 — buildOperatorImmunity", () => {
  it("baseline (empty inputs) emits HIGH immunity + all-strong sub-fields + steady summary", () => {
    const { currState, diff, stability, resilience } = chain("", "");
    const out = buildOperatorImmunity(currState, diff, stability, resilience);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Immunity ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Immunity Level]")).toBeGreaterThan(idx("=== Operator Immunity ==="));
    expect(idx("[Operator Resistance]")).toBeGreaterThan(idx("[Immunity Level]"));
    expect(idx("[Operator Shielding]")).toBeGreaterThan(idx("[Operator Resistance]"));
    expect(idx("[Drift-Immunity]")).toBeGreaterThan(idx("[Operator Shielding]"));
    expect(idx("[Clarity-Immunity]")).toBeGreaterThan(idx("[Drift-Immunity]"));
    expect(idx("[Load-Immunity]")).toBeGreaterThan(idx("[Clarity-Immunity]"));
    expect(idx("[Pressure-Immunity]")).toBeGreaterThan(idx("[Load-Immunity]"));
    expect(idx("[Immunity Trajectory]")).toBeGreaterThan(idx("[Pressure-Immunity]"));
    expect(idx("[Immunity Drivers]")).toBeGreaterThan(idx("[Immunity Trajectory]"));
    expect(idx("[Immunity Inhibitors]")).toBeGreaterThan(idx("[Immunity Drivers]"));
    expect(idx("[Immunity Risks]")).toBeGreaterThan(idx("[Immunity Inhibitors]"));
    expect(idx("[Immunity Reinforcement]")).toBeGreaterThan(idx("[Immunity Risks]"));
    expect(idx("[Immunity Decay]")).toBeGreaterThan(idx("[Immunity Reinforcement]"));
    expect(idx("[Operator Immunity Summary]")).toBeGreaterThan(idx("[Immunity Decay]"));

    // All-optimal baseline.
    expect(out).toContain("[Immunity Level]\nHIGH");
    expect(out).toContain("[Operator Resistance]\nstrong");
    expect(out).toContain("[Operator Shielding]\nstrong");
    expect(out).toContain("[Drift-Immunity]\nstrong");
    expect(out).toContain("[Clarity-Immunity]\nstrong");
    expect(out).toContain("[Load-Immunity]\nstrong");
    expect(out).toContain("[Pressure-Immunity]\nstrong");
    expect(out).toContain("[Immunity Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Immunity Risks]\n(none)");
    // Decay lines fire even at baseline — they describe forward-
    // looking failure modes the operator could still drift into.
    expect(out).toContain("- drift may increase");
    expect(out).toContain("- pressure may spike");
    expect(out).toContain("- clarity may weaken");
    expect(out).toContain("Operator immunity is steady. Drift-immunity is strong, clarity-immunity is strong, and shielding is strong.");
  });

  it("strong drift-immunity scenario: drift=low (default) reports strong drift-immunity", () => {
    // Use a non-baseline scenario where pressure causes some inhibitors
    // but drift remains low → drift-immunity should still be strong.
    const { currState, diff, stability, resilience } = chain("", "pressure=moderate");
    const out = buildOperatorImmunity(currState, diff, stability, resilience);

    expect(out).toContain("[Drift-Immunity]\nstrong");
    // pressure=moderate → pressure-immunity=moderate.
    expect(out).toContain("[Pressure-Immunity]\nmoderate");
  });

  it("weak pressure-immunity scenario: pressure=high reports weak pressure-immunity + deteriorating direction", () => {
    const { currState, diff, stability, resilience } = chain("", "pressure=high");
    const out = buildOperatorImmunity(currState, diff, stability, resilience);

    expect(out).toContain("[Pressure-Immunity]\nweak");
    // High pressure adds operator-overload + drift-reactivation risks.
    expect(out).toContain("- operator overload");
    expect(out).toContain("- drift reactivation");
    // Deteriorating direction + high pressure → deteriorating summary.
    expect(out).toContain("Operator immunity is deteriorating under high pressure.");
  });

  it("moderate shielding scenario: mixed dims (some optimal, some not) reports moderate shielding", () => {
    // load=moderate (not optimal) + drift=low + clarity=strong + pressure=low
    // → 3 optimal dims out of 4 → moderate shielding.
    const { currState, diff, stability, resilience } = chain("", "load=moderate");
    const out = buildOperatorImmunity(currState, diff, stability, resilience);

    expect(out).toContain("[Operator Shielding]\nmoderate");
    expect(out).toContain("[Load-Immunity]\nmoderate");
    expect(out).toContain("[Drift-Immunity]\nstrong");
    expect(out).toContain("[Clarity-Immunity]\nstrong");
  });

  it("summary correctness: improving + pressure=elevated + clarity=partial mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator immunity is improving but remains vulnerable to
    //    elevated pressure. Drift-immunity is strong, clarity-
    //    immunity is partial, and shielding is moderate."
    // Engineer prev/curr so the level actually moves up (improving
    // direction registers via prev<curr level comparison).
    const prevInput = "clarity=weak stability=weak load=high drift=high";
    const currInput = "load=moderate drift=low clarity=partial stability=moderate pressure=elevated direction=improving";
    const { currState, diff, stability, resilience } = chain(prevInput, currInput);
    const out = buildOperatorImmunity(currState, diff, stability, resilience);

    expect(out).toContain("[Drift-Immunity]\nstrong");
    expect(out).toContain("[Clarity-Immunity]\npartial");
    expect(out).toContain("[Load-Immunity]\nmoderate");
    expect(out).toContain("[Pressure-Immunity]\nweak");
    expect(out).toContain("[Operator Shielding]\nmoderate");
    expect(out).toContain(
      "Operator immunity is improving but remains vulnerable to elevated pressure. Drift-immunity is strong, clarity-immunity is partial, and shielding is moderate.",
    );
    // Drivers + inhibitors carry over Card 69's spec-demo wording.
    expect(out).toContain("- improving clarity");
    expect(out).toContain("- reduced drift");
    expect(out).toContain("- improved load distribution");
    expect(out).toContain("- elevated pressure");
    expect(out).toContain("- partial clarity");
    expect(out).toContain("- residual drift");
  });
});
