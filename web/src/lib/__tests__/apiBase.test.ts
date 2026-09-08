/**
 * #175 -- the SPA calls the backend on the SAME origin: /api, which the URL
 * map routes to clarity-engine (pathPrefixRewrite /). No preflight. The
 * env file is tracked (an ignore exception): the base ships with the sha.
 */
import { describe, it, expect } from "vitest";
import env from "../../../.env.production?raw";

describe("the API base (#175)", () => {
  it("\u2605 the production env bakes /api, not the run.app origin", () => {
    const line = env.split(/\r?\n/).find((l: string) => l.startsWith("VITE_API_BASE="));
    expect(line).toBe("VITE_API_BASE=/api");
    expect(line).not.toMatch(/https?:/);   // the VALUE is a path, never an origin
  });
});
