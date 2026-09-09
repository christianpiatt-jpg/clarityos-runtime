/**
 * #162 (e)(d)(a)(b) -- the dictionary, the rail sentence, the bearing rows,
 * the stop mark. Pure functions; pinned by value.
 */
import { describe, it, expect } from "vitest";
import { LABELS, labelFor, labelText } from "../labels";
import { trustLine, AWAITING_SECOND_READ } from "../trustSignal";
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

describe("trustLine -- the ONE line speaks trust_signal's status (#167c)", () => {
  const base = { scored_turns: 0, theta_floor: 7, theta_ready: false };
  it("no signal / no_prior_yet -> trust — with the sentence and the floor", () => {
    expect(trustLine(null)).toBe(`trust — · ${AWAITING_SECOND_READ} (floor 7)`);
    expect(trustLine(undefined)).toBe(`trust — · ${AWAITING_SECOND_READ} (floor 7)`);
    expect(trustLine({ status: "no_prior_yet", ...base })).toBe(`trust — · ${AWAITING_SECOND_READ} (floor 7)`);
  });
  it("undefined -> the words; a value -> value · n scored, the sentence while theta is not ready", () => {
    expect(trustLine({ status: "undefined", ...base })).toBe("trust undefined (no bearing claimed)");
    expect(trustLine({ ...base, status: "value", value: 0.5, scored_turns: 1 } as never)).toBe(`trust 0.5 · 1 scored · ${AWAITING_SECOND_READ} (floor 7)`);
    expect(trustLine({ status: "value", value: 1, scored_turns: 8, theta_floor: 7, theta_ready: true } as never)).toBe("trust 1 · 8 scored");
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
  it("#196 -- the stop mark only for a stop the ONE vocabulary called a cut", () => {
    // #196 -- ONLY the backend vocabulary's "cut" marks. The raw token
    // is what the mark NAMES; the class is what decides.
    expect(stopMark("max_tokens", "cut")).toBe("max_tokens");
    expect(stopMark("length", "cut")).toBe("length");
    expect(stopMark("SAFETY", "cut")).toBe("SAFETY");
    // the #196 bug: a NORMAL finish from OpenAI / Gemini / Ollama
    expect(stopMark("stop", "normal")).toBeNull();
    expect(stopMark("STOP", "normal")).toBeNull();
    expect(stopMark("end_turn", "normal")).toBeNull();
    // the other direction: a word the table does not know is NOT a cut
    expect(stopMark("tool_use", "unknown")).toBeNull();
    // no class at all (a mock, an older wire) marks nothing
    expect(stopMark("max_tokens", undefined)).toBeNull();
    expect(stopMark("max_tokens", null)).toBeNull();
    expect(stopMark(null, "cut")).toBeNull();
    expect(stopMark("", "cut")).toBeNull();
  });
});
