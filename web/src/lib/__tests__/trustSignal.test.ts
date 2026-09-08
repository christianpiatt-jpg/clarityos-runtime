/**
 * #167c -- ONE trust line for the one trust object. The four shapes.
 */
import { describe, it, expect } from "vitest";
import { trustLine, AWAITING_SECOND_READ } from "../trustSignal";

const base = { scored_turns: 0, theta_floor: 7, theta_ready: false };

describe("trustLine -- one measure, one line, one name", () => {
  it("no signal / no_prior_yet -> trust — with the awaiting sentence and the floor", () => {
    expect(trustLine(null)).toBe(`trust — · ${AWAITING_SECOND_READ} (floor 7)`);
    expect(trustLine(undefined)).toBe("trust — · awaiting a second read (floor 7)");
    expect(trustLine({ status: "no_prior_yet", ...base })).toBe("trust — · awaiting a second read (floor 7)");
  });
  it("undefined -> the words, no number", () => {
    expect(trustLine({ status: "undefined", ...base, scored_turns: 2 })).toBe("trust undefined (no bearing claimed)");
  });
  it("a value while theta is not ready -> value · n scored · the sentence with the floor", () => {
    expect(trustLine({ ...base, status: "value", value: 0.8333, scored_turns: 2 } as never))
      .toBe("trust 0.8333 · 2 scored · awaiting a second read (floor 7)");
  });
  it("a value once theta is ready -> no tail; the floor from the signal", () => {
    expect(trustLine({ status: "value", value: 1, scored_turns: 9, theta_floor: 9, theta_ready: true } as never))
      .toBe("trust 1 · 9 scored");
    expect(trustLine({ status: "no_prior_yet", scored_turns: 0, theta_floor: 9, theta_ready: false }))
      .toBe("trust — · awaiting a second read (floor 9)");
  });
  it("the direction is not on the line (one measure) and basin_hop is gone", () => {
    const line = trustLine({ ...base, status: "value", value: 0.5, direction: "rising", scored_turns: 3 } as never);
    expect(line).not.toMatch(/rising|basin_hop/);
    expect(line).toBe("trust 0.5 · 3 scored · awaiting a second read (floor 7)");
  });
});
