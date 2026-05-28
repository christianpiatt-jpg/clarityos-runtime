// Card 24 — buildEngineRunRequest pure-function test.
//
// Verifies the canonical Engine V1 input builder:
//   1. forwards primitives verbatim
//   2. defaults projection_days to 7 when omitted
//   3. accepts an explicit projectionDays override
//   4. produces a shape that matches EngineRunRequest exactly
//
// No mocking, no fetch, no session. Pure unit test.

import { describe, expect, it } from "vitest";

import {
  buildEngineRunRequest,
  type EnginePrimitiveInput,
  type EngineRunRequest,
} from "../api";

function minimalPrimitive(): EnginePrimitiveInput {
  return { pressure: 5.0, flow: 4.0, resistance: 2.0 };
}

describe("Card 24 — buildEngineRunRequest", () => {
  it("returns the canonical EngineRunRequest shape from primitives", () => {
    const primitives: EnginePrimitiveInput[] = [minimalPrimitive()];

    const request: EngineRunRequest = buildEngineRunRequest(primitives);

    expect(request.primitives).toBe(primitives);
    expect(request.projection_days).toBe(7);
    // Shape contains exactly the two contract keys — no extras.
    expect(Object.keys(request).sort()).toEqual(
      ["primitives", "projection_days"].sort(),
    );
  });

  it("defaults projection_days to 7 when projectionDays omitted", () => {
    const request = buildEngineRunRequest([]);
    expect(request.projection_days).toBe(7);
  });

  it("uses the explicit projectionDays argument when provided", () => {
    const request = buildEngineRunRequest([minimalPrimitive()], 30);
    expect(request.projection_days).toBe(30);
  });

  it("accepts zero as a valid projectionDays (not coerced to default)", () => {
    // 0 is falsy in JS — pin that the builder uses the default-parameter
    // mechanism (only undefined triggers the default), not a truthy check.
    const request = buildEngineRunRequest([], 0);
    expect(request.projection_days).toBe(0);
  });

  it("passes primitives through by reference (no defensive copy)", () => {
    // Phase-1 is intentionally pass-through. If a future card adds a
    // defensive copy or validation pass, this test should fail and be
    // updated deliberately.
    const primitives: EnginePrimitiveInput[] = [minimalPrimitive()];
    const request = buildEngineRunRequest(primitives, 7);
    expect(request.primitives).toBe(primitives);
  });

  it("accepts a fully-specified primitive without mutating it", () => {
    const fullPrimitive: EnginePrimitiveInput = {
      primitive_id:   "prim_24_001",
      primitive_type: "signal",
      domain:         "general",
      source:         "Card 24 test",
      content:        { note: "fixture" },
      pressure:       5.0,
      flow:           4.0,
      resistance:     2.0,
      gradient:       0.1,
    };
    const snapshot = JSON.stringify(fullPrimitive);

    const request = buildEngineRunRequest([fullPrimitive], 14);

    expect(request.primitives[0]).toBe(fullPrimitive);
    expect(JSON.stringify(fullPrimitive)).toBe(snapshot);  // untouched
    expect(request.projection_days).toBe(14);
  });
});
