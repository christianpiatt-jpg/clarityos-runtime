/**
 * #162 (e)(d)(a)(b) -- the dictionary, the rail sentence, the bearing rows,
 * the stop mark. Pure functions; pinned by value.
 */
import { describe, it, expect } from "vitest";
import { LABELS, labelFor, labelText } from "../labels";
import { basinHopLine, AWAITING_SECOND_READ } from "../trustSignal";
import { bearingRows, stopMark } from "../bearings";

describe("labels -- one dictionary, never blank", () => {
  it("carries CT-1's words for the minimum set", () => {
    expect(labelFor("attractor")).toEqual({ word: "what's pulling", instrument: "elins" });
    expect(labelFor("collapse_state")).toEqual({ word: "holding / giving", instrument: "elins" });
    expect(labelFor("L6_drift").word).toBe("drift");
    expect(labelFor("pressure_level")).toEqual({ word: "pressure", instrument: "azimuth" });
    for (const k of ["trust", "alignment", "boundary", "agency", "distance"]) {
      expect(labelFor(k).instrument).toBe("physics \u00b7 model-read");
      expect(labelFor(k).word).toBe(k);
    }
  });
  it("an unknown key comes back as itself, never blank", () => {
    expect(labelFor("basin_hop")).toEqual({ word: "basin_hop", instrument: "" });
    expect(labelText("some_new_key")).toBe("some_new_key");
    expect(labelText("")).not.toBe("");
  });
  it("carries the minimum set the order named, and the physics header key", () => {
    for (const k of ["attractor", "collapse_state", "L6_drift", "L5_pressure", "L9_alignment",
                     "trust", "alignment", "boundary", "agency", "distance", "pressure_level",
                     "relational_primitives"]) {
      expect(LABELS[k]).toBeDefined();
    }
  });
  it("a whitespace-only bearing is missing, like an absent one", async () => {
    const rows = bearingRows({ trust: "   " as never });
    expect(rows[0]).toMatchObject({ key: "trust", value: "\u2014", missing: true });
  });
});

describe("basinHopLine -- the rail speaks trust_signal's status", () => {
  const base = { scored_turns: 0, theta_floor: 7, theta_ready: false };
  it("no signal / no_prior_yet -> the sentence", () => {
    expect(basinHopLine(null)).toBe(`basin_hop -- ${AWAITING_SECOND_READ}`);
    expect(basinHopLine(undefined)).toBe(`basin_hop -- ${AWAITING_SECOND_READ}`);
    expect(basinHopLine({ status: "no_prior_yet", ...base })).toBe(`basin_hop -- ${AWAITING_SECOND_READ}`);
  });
  it("n = 1 -> the value, no direction, the sentence kept beside it (theta not ready)", () => {
    const line = basinHopLine({ status: "value", value: 0.8333, scored_turns: 1, per_turn: [0.8333], theta_floor: 7, theta_ready: false });
    expect(line).toBe(`basin_hop -- trust 0.8333 \u00b7 ${AWAITING_SECOND_READ}`);
    expect(line).not.toMatch(/rising|falling|flat/);
  });
  it("a direction rides when sent; theta ready drops the sentence", () => {
    expect(basinHopLine({ status: "value", value: 0.5, direction: "falling", delta: -0.5, scored_turns: 2, theta_floor: 7, theta_ready: false }))
      .toBe(`basin_hop -- trust 0.5 \u00b7 falling \u00b7 ${AWAITING_SECOND_READ}`);
    expect(basinHopLine({ status: "value", value: 0.9, direction: "rising", delta: 0.1, scored_turns: 7, theta_floor: 7, theta_ready: true }))
      .toBe("basin_hop -- trust 0.9 \u00b7 rising");
  });
  it("undefined is a different kind, named", () => {
    expect(basinHopLine({ status: "undefined", scored_turns: 1, theta_floor: 7, theta_ready: false }))
      .toBe("basin_hop -- trust undefined (no bearing claimed)");
  });
});

describe("bearingRows / stopMark", () => {
  it("five rows in order; a missing key is an em dash, unclear is the word", () => {
    const rows = bearingRows({ trust: "high", alignment: "unclear", boundary: "soft", agency: "partial" });
    expect(rows.map((r) => r.key)).toEqual(["trust", "alignment", "boundary", "agency", "distance"]);
    expect(rows[0].value).toBe("high");
    expect(rows[1].value).toBe("unclear");
    expect(rows[4]).toMatchObject({ key: "distance", value: "\u2014", missing: true });
  });
  it("an empty layer ({} after a parse failure) is five dashes, never 0.0", () => {
    const rows = bearingRows({});
    expect(rows.every((r) => r.missing && r.value === "\u2014")).toBe(true);
    expect(bearingRows(undefined).length).toBe(5);
  });
  it("the stop mark only for a stop other than end_turn", () => {
    expect(stopMark("end_turn")).toBeNull();
    expect(stopMark(null)).toBeNull();
    expect(stopMark(undefined)).toBeNull();
    expect(stopMark("")).toBeNull();
    expect(stopMark("max_tokens")).toBe("max_tokens");
  });
});
