// Card 72 — Operator Resilience engine unit tests.
//
// Builds state + diff + stability fixtures via Cards 69/70/71
// directly so the test inputs stay tied to the canonical upstream
// outputs. Covers the five spec scenarios: baseline, high-pressure
// recovery, strong drift-recovery, weak clarity-recovery, and
// summary correctness.

import { describe, expect, it } from "vitest";

import { buildOperatorState }      from "../operatorState";
import { buildOperatorDiff }       from "../operatorStateDiff";
import { buildOperatorStability }  from "../operatorStability";
import { buildOperatorResilience } from "../operatorResilience";

describe("Card 72 — buildOperatorResilience", () => {
  it("baseline (empty state) emits HIGH resilience with all-strong recoveries + steady summary", () => {
    const state = buildOperatorState("");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const stab  = buildOperatorStability(state, diff);
    const out   = buildOperatorResilience(state, diff, stab);

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Operator Resilience ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Resilience Level]")).toBeGreaterThan(idx("=== Operator Resilience ==="));
    expect(idx("[Operator Recovery]")).toBeGreaterThan(idx("[Resilience Level]"));
    expect(idx("[Operator Rebound]")).toBeGreaterThan(idx("[Operator Recovery]"));
    expect(idx("[Drift-Recovery]")).toBeGreaterThan(idx("[Operator Rebound]"));
    expect(idx("[Clarity-Recovery]")).toBeGreaterThan(idx("[Drift-Recovery]"));
    expect(idx("[Load-Recovery]")).toBeGreaterThan(idx("[Clarity-Recovery]"));
    expect(idx("[Pressure-Recovery]")).toBeGreaterThan(idx("[Load-Recovery]"));
    expect(idx("[Resilience Trajectory]")).toBeGreaterThan(idx("[Pressure-Recovery]"));
    expect(idx("[Resilience Drivers]")).toBeGreaterThan(idx("[Resilience Trajectory]"));
    expect(idx("[Resilience Inhibitors]")).toBeGreaterThan(idx("[Resilience Drivers]"));
    expect(idx("[Resilience Risks]")).toBeGreaterThan(idx("[Resilience Inhibitors]"));
    expect(idx("[Resilience Reinforcement]")).toBeGreaterThan(idx("[Resilience Risks]"));
    expect(idx("[Resilience Decay]")).toBeGreaterThan(idx("[Resilience Reinforcement]"));
    expect(idx("[Operator Resilience Summary]")).toBeGreaterThan(idx("[Resilience Decay]"));

    // HIGH baseline derived fields.
    expect(out).toContain("[Resilience Level]\nHIGH");
    expect(out).toContain("[Operator Recovery]\nstrong");
    expect(out).toContain("[Operator Rebound]\nstrong");
    expect(out).toContain("[Drift-Recovery]\nstrong");
    expect(out).toContain("[Clarity-Recovery]\nstrong");
    expect(out).toContain("[Load-Recovery]\nstrong");
    expect(out).toContain("[Pressure-Recovery]\nstrong");
    expect(out).toContain("[Resilience Trajectory]\nhigh → high → high (stable)");
    expect(out).toContain("[Resilience Drivers]\n(none)");
    expect(out).toContain("[Resilience Inhibitors]\n(none)");
    expect(out).toContain("[Resilience Risks]\n(none)");
    expect(out).toContain("Operator resilience is steady. Drift-recovery is strong, clarity-recovery is strong, and rebound is strong.");
  });

  it("high-pressure recovery scenario: pressure=high → pressure-recovery=weak + deteriorating summary", () => {
    const state = buildOperatorState("pressure=high");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const stab  = buildOperatorStability(state, diff);
    const out   = buildOperatorResilience(state, diff, stab);

    expect(out).toContain("[Pressure-Recovery]\nweak");
    // Operator Recovery weakens when direction is deteriorating.
    expect(out).toContain("[Operator Recovery]\nweak");
    // Resilience risks fire under high pressure.
    expect(out).toContain("- operator overload");
    expect(out).toContain("- drift reactivation");
    // Summary references deteriorating + high pressure.
    expect(out).toContain("Operator resilience is deteriorating under high pressure.");
  });

  it("strong drift-recovery scenario: drift=low (the default) yields strong drift-recovery", () => {
    // Even when other dims are weakened, drift-recovery stays strong
    // because drift itself is at the optimal floor.
    const state = buildOperatorState("pressure=elevated clarity=weak");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const stab  = buildOperatorStability(state, diff);
    const out   = buildOperatorResilience(state, diff, stab);

    expect(out).toContain("[Drift-Recovery]\nstrong");
    // Clarity-recovery weak (clarity=weak in state).
    expect(out).toContain("[Clarity-Recovery]\nweak");
    expect(out).toContain("[Pressure-Recovery]\nweak");
  });

  it("weak clarity-recovery scenario: clarity=weak → clarity-recovery=weak + clarity-degradation risk", () => {
    const state = buildOperatorState("clarity=weak");
    const diff  = buildOperatorDiff(buildOperatorState(""), state);
    const stab  = buildOperatorStability(state, diff);
    const out   = buildOperatorResilience(state, diff, stab);

    expect(out).toContain("[Clarity-Recovery]\nweak");
    // Risks fire for clarity degradation.
    expect(out).toContain("- clarity degradation");
    // Drift-recovery + load-recovery + pressure-recovery still strong
    // because those dims default to optimal.
    expect(out).toContain("[Drift-Recovery]\nstrong");
    expect(out).toContain("[Load-Recovery]\nstrong");
    expect(out).toContain("[Pressure-Recovery]\nstrong");
  });

  it("summary correctness: improving + pressure=elevated mirrors spec demo phrasing", () => {
    // Spec demo:
    //   "Operator resilience is improving but remains vulnerable to
    //    elevated pressure. Drift-recovery is strong, clarity-recovery
    //    is partial, and rebound is moderate."
    //
    // Engineer prev/curr so direction registers as improving and the
    // current dims match the spec-demo values.
    const prev = buildOperatorState("clarity=weak stability=weak load=high drift=high");
    const curr = buildOperatorState(
      "load=moderate drift=low clarity=partial stability=moderate pressure=elevated direction=improving",
    );
    const diff = buildOperatorDiff(prev, curr);
    const stab = buildOperatorStability(curr, diff);
    const out  = buildOperatorResilience(curr, diff, stab);

    expect(out).toContain("[Drift-Recovery]\nstrong");
    expect(out).toContain("[Clarity-Recovery]\npartial");
    expect(out).toContain("[Operator Rebound]\nmoderate");
    expect(out).toContain("[Load-Recovery]\nmoderate");
    expect(out).toContain("[Pressure-Recovery]\nweak");
    expect(out).toContain(
      "Operator resilience is improving but remains vulnerable to elevated pressure. Drift-recovery is strong, clarity-recovery is partial, and rebound is moderate.",
    );
  });
});
