// Card 71 — Operator Stability engine unit tests.
//
// Builds state + diff fixtures via Card 69/70 helpers directly so
// the test inputs stay tied to the canonical upstream outputs.
// Covers the five spec scenarios: baseline, high-volatility, high-
// pressure instability, strong drift-stability, and summary
// correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }     from "../operatorState";
import { buildOperatorDiff }      from "../operatorStateDiff";
import { buildOperatorStability } from "../operatorStability";

describe("Card 71 — buildOperatorStability", () => {
  it("baseline (empty state + empty diff) emits HIGH stability with all-optimal sub-fields + steady summary", () => {
    const state = buildOperatorState("");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const out   = buildOperatorStability(state, diff);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Stability ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Stability Level]")).toBeGreaterThan(idx("=== Operator Stability ==="));
    expect(idx("[Operator Equilibrium]")).toBeGreaterThan(idx("[Stability Level]"));
    expect(idx("[Operator Volatility]")).toBeGreaterThan(idx("[Operator Equilibrium]"));
    expect(idx("[Drift-Stability]")).toBeGreaterThan(idx("[Operator Volatility]"));
    expect(idx("[Clarity-Stability]")).toBeGreaterThan(idx("[Drift-Stability]"));
    expect(idx("[Load-Stability]")).toBeGreaterThan(idx("[Clarity-Stability]"));
    expect(idx("[Pressure-Stability]")).toBeGreaterThan(idx("[Load-Stability]"));
    expect(idx("[Stability Trajectory]")).toBeGreaterThan(idx("[Pressure-Stability]"));
    expect(idx("[Stability Drivers]")).toBeGreaterThan(idx("[Stability Trajectory]"));
    expect(idx("[Stability Inhibitors]")).toBeGreaterThan(idx("[Stability Drivers]"));
    expect(idx("[Stability Risks]")).toBeGreaterThan(idx("[Stability Inhibitors]"));
    expect(idx("[Stability Reinforcement]")).toBeGreaterThan(idx("[Stability Risks]"));
    expect(idx("[Stability Decay]")).toBeGreaterThan(idx("[Stability Reinforcement]"));
    expect(idx("[Operator Stability Summary]")).toBeGreaterThan(idx("[Stability Decay]"));

    // Derived fields for HIGH baseline.
    expect(out).toContain("[Stability Level]\nHIGH");
    expect(out).toContain("[Operator Equilibrium]\nstrong");
    expect(out).toContain("[Operator Volatility]\nlow");
    expect(out).toContain("[Drift-Stability]\nstrong");
    expect(out).toContain("[Clarity-Stability]\nstrong");
    expect(out).toContain("[Load-Stability]\nstrong");
    expect(out).toContain("[Pressure-Stability]\nstrong");
    expect(out).toContain("[Stability Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Stability Drivers]\n(none)");
    expect(out).toContain("[Stability Inhibitors]\n(none)");
    expect(out).toContain("[Stability Risks]\n(none)");
    // All four reinforcement lines fire (none of the dims are at
    // their critical worst).
    expect(out).toContain("- maintain clarity focus");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain load balance");
    expect(out).toContain("- maintain pressure control");
    expect(out).toContain("Operator stability is steady. Drift-stability is strong, clarity-stability is strong, and volatility is low.");
  });

  it("high-volatility scenario: pressure=high + drift=high → volatility=high + Stability Level drops", () => {
    const state = buildOperatorState("pressure=high drift=high clarity=weak");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const out   = buildOperatorStability(state, diff);

    expect(out).toContain("[Operator Volatility]\nhigh");
    // operatorLevel goes deep into LOW territory, then -1 for high
    // volatility clamps at 0 → LOW.
    expect(out).toContain("[Stability Level]\nLOW");
    expect(out).toContain("[Drift-Stability]\nweak");
    expect(out).toContain("[Clarity-Stability]\nweak");
    expect(out).toContain("[Pressure-Stability]\nweak");
    // 3 critical signals → equilibrium=weak.
    expect(out).toContain("[Operator Equilibrium]\nweak");
  });

  it("high-pressure instability: pressure=high → pressure-stability=weak + summary mentions deteriorating + high pressure", () => {
    const state = buildOperatorState("pressure=high");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const out   = buildOperatorStability(state, diff);

    expect(out).toContain("[Pressure-Stability]\nweak");
    // pressure=elevated risks fire (overload + drift reactivation +
    // clarity degradation only if clarity isn't strong — here it's
    // strong so we skip clarity-degradation).
    expect(out).toContain("- operator overload");
    expect(out).toContain("- drift reactivation");
    // Direction inferred from the Card 70 diff summary (which says
    // "deteriorating under high pressure" for this fixture).
    expect(out).toContain("Operator stability is deteriorating under high pressure.");
  });

  it("strong drift-stability: drift=low (the default) yields strong drift-stability for any non-drift scenario", () => {
    // Even with elevated pressure and weak clarity, drift-stability
    // stays strong as long as drift is low.
    const state = buildOperatorState("pressure=elevated clarity=weak");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const out   = buildOperatorStability(state, diff);

    expect(out).toContain("[Drift-Stability]\nstrong");
    // Other dims show their non-optimal status.
    expect(out).toContain("[Clarity-Stability]\nweak");
    expect(out).toContain("[Pressure-Stability]\nweak");
  });

  it("summary correctness: improving + pressure=elevated mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator stability is improving but remains vulnerable to
    //    elevated pressure. Drift-stability is strong, clarity-
    //    stability is partial, and volatility is moderate."
    //
    // Engineer prev/curr so direction registers as improving (prev
    // operator level < curr operator level) and curr matches the
    // spec demo dim values.
    const prev = buildOperatorState("clarity=weak stability=weak load=high drift=high");
    const curr = buildOperatorState(
      "load=moderate drift=low clarity=partial stability=moderate pressure=elevated direction=improving",
    );
    const diff = buildOperatorDiff(prev, curr);
    const out  = buildOperatorStability(curr, diff);

    expect(out).toContain("[Drift-Stability]\nstrong");
    expect(out).toContain("[Clarity-Stability]\npartial");
    expect(out).toContain("[Operator Volatility]\nmoderate");
    expect(out).toContain("[Load-Stability]\nmoderate");
    expect(out).toContain("[Pressure-Stability]\nweak");
    expect(out).toContain(
      "Operator stability is improving but remains vulnerable to elevated pressure. Drift-stability is strong, clarity-stability is partial, and volatility is moderate.",
    );
  });
});
