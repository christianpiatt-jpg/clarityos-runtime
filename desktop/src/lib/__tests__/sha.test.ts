/** #167b -- the sha fence. */
import { describe, it, expect } from "vitest";
import { normSha, shortSha } from "../sha";

describe("normSha / shortSha", () => {
  it("\u2605 unknown is not a sha; the caption is seven characters", () => {
    expect(normSha("unknown")).toBeNull();
    expect(normSha(" ABC ")).toBe("abc");
    expect(shortSha("bb23e509ae3cad3156103d3d4fa47caa9974ada5")).toBe("bb23e50");
    expect(shortSha(null)).toBe("unknown");
  });
});
