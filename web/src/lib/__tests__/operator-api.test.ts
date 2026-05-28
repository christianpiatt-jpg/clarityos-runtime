// Card 39 — createEngineV1OperatorAPI surface test.
//
// Asserts the Operator Console API:
//   1. exposes every documented key
//   2. each value is a function
//   3. each field is the SAME REFERENCE as the underlying helper
//      (proves identity-delegation; no wrapping, no adapter drift)
//   4. produces structurally identical APIs on repeated calls
//      (determinism / no hidden state)
//
// Pure unit test — no fetch, no session. The factory is pure
// composition over already-tested helpers, so we don't re-test the
// helpers themselves here.

import { describe, expect, it } from "vitest";

import {
  buildHydraulicEvolutionMap,
  buildLineageMap,
  buildPrimitiveLineageOverlay,
  buildSystemOverlay,
  computeEngineV1Delta,
  computeSystemRegressionDiff,
  createEngineV1Context,
  createEngineV1OperatorAPI,
  createMultiRunContext,
  diffPrimitiveLineage,
  extractPrimitiveLineage,
  type EngineV1OperatorAPI,
} from "../api";

const EXPECTED_KEYS = [
  "createContext",
  "createMultiRunContext",
  "computeDelta",
  "extractLineage",
  "diffLineage",
  "buildLineageOverlay",
  "buildLineageMap",
  "buildHydraulicEvolution",
  "buildSystemOverlay",
  "computeSystemRegression",
] as const;

describe("Card 39 — createEngineV1OperatorAPI", () => {
  it("exposes every documented key", () => {
    const api: EngineV1OperatorAPI = createEngineV1OperatorAPI();
    expect(Object.keys(api).sort()).toEqual([...EXPECTED_KEYS].sort());
  });

  it("every key is a function", () => {
    const api = createEngineV1OperatorAPI();
    for (const key of EXPECTED_KEYS) {
      expect(typeof api[key], `${key} should be a function`).toBe("function");
    }
  });

  it("each field delegates by identity to the underlying helper", () => {
    // Identity-equality proves the factory is pure delegation — no
    // wrappers were inserted that could drift from the source helper.
    const api = createEngineV1OperatorAPI();
    expect(api.createContext).toBe(createEngineV1Context);
    expect(api.createMultiRunContext).toBe(createMultiRunContext);
    expect(api.computeDelta).toBe(computeEngineV1Delta);
    expect(api.extractLineage).toBe(extractPrimitiveLineage);
    expect(api.diffLineage).toBe(diffPrimitiveLineage);
    expect(api.buildLineageOverlay).toBe(buildPrimitiveLineageOverlay);
    expect(api.buildLineageMap).toBe(buildLineageMap);
    expect(api.buildHydraulicEvolution).toBe(buildHydraulicEvolutionMap);
    expect(api.buildSystemOverlay).toBe(buildSystemOverlay);
    expect(api.computeSystemRegression).toBe(computeSystemRegressionDiff);
  });

  it("produces structurally identical APIs across calls (determinism)", () => {
    // The factory has no hidden state — two invocations should yield
    // objects with the same key set + the same function references
    // for every key.
    const a = createEngineV1OperatorAPI();
    const b = createEngineV1OperatorAPI();
    expect(Object.keys(a).sort()).toEqual(Object.keys(b).sort());
    for (const key of EXPECTED_KEYS) {
      expect(a[key]).toBe(b[key]);
    }
  });

  it("returns a fresh object on each call (no shared mutation surface)", () => {
    // Different object identity, identical contents — so a caller
    // mutating one returned API can't corrupt a sibling caller's.
    const a = createEngineV1OperatorAPI();
    const b = createEngineV1OperatorAPI();
    expect(a).not.toBe(b);
    expect(a).toEqual(b);
  });
});
