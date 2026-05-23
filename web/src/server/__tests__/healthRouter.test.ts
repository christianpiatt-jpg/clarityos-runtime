// @vitest-environment node
//
// Track C — health/ready router tests.
//
// Three surfaces under test:
//
//   1. HEALTH_PAYLOAD constant shape.
//   2. handleHealth() Response shape (status / headers / body).
//   3. HEALTH_PATHS contains both /health and /ready.
//
// Determinism is the load-bearing property — health/ready
// responses must be byte-identical regardless of env, clock,
// or surface state.
//
// Path: web/src/server/__tests__/healthRouter.test.ts
import { describe, expect, test } from "vitest";

import {
  HEALTH_PAYLOAD,
  HEALTH_PATHS,
  handleHealth,
  HealthPayload,
} from "../healthRouter";


describe("HEALTH_PAYLOAD constant", () => {
  test("has the exact spec shape", () => {
    expect(HEALTH_PAYLOAD).toEqual({
      status:  "ok",
      surface: "v0.2.0",
    });
  });

  test("matches the HealthPayload type", () => {
    // Compile-time guard: if HealthPayload diverges from
    // HEALTH_PAYLOAD's shape, this assignment fails to type-check.
    const _typed: HealthPayload = HEALTH_PAYLOAD;
    expect(_typed.status).toBe("ok");
    expect(_typed.surface).toBe("v0.2.0");
  });
});


describe("HEALTH_PATHS", () => {
  test("contains both /health and /ready (full path-bypass set)", () => {
    expect([...HEALTH_PATHS].sort()).toEqual(["/health", "/ready"]);
  });

  test("paths begin with '/' (matches Node req.url shape)", () => {
    for (const p of HEALTH_PATHS) {
      expect(p.startsWith("/")).toBe(true);
    }
  });
});


describe("handleHealth", () => {
  test("returns 200 + application/json + HEALTH_PAYLOAD body", () => {
    const res = handleHealth();
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual(HEALTH_PAYLOAD);
  });

  test("is deterministic — same call → same Response", () => {
    const a = handleHealth();
    const b = handleHealth();
    expect(a).toEqual(b);
  });

  test("returns a fresh Response each call (no shared mutation surface)", () => {
    const a = handleHealth();
    const b = handleHealth();
    expect(a).not.toBe(b);
    expect(a.headers).not.toBe(b.headers);
  });

  test("body shape JSON-stringifies to a canonical bytes form", () => {
    // The HTTP adapter will JSON-stringify the body object; we
    // pre-flight that here so any change to the JSON shape
    // surfaces as a test failure.
    expect(JSON.stringify(handleHealth().body))
      .toBe('{"status":"ok","surface":"v0.2.0"}');
  });
});
