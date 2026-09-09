/** #167b -- five rows: missing "—", "unclear" the word, false the word; the stop mark. */
import { describe, it, expect } from "vitest";
import { bearingRows, stopMark } from "../bearings";

describe("bearingRows", () => {
  it("\u2605 five rows in order; missing -> —; unclear -> the word; false -> the word", () => {
    const rows = bearingRows({ trust: "low", alignment: "unclear", boundary: "   ", agency: false, notes: "prose" });
    expect(rows.map((r) => r.key)).toEqual(["trust", "alignment", "boundary", "agency", "distance"]);
    expect(rows[0]).toMatchObject({ label: "trust", value: "low", missing: false });
    expect(rows[1]).toMatchObject({ value: "unclear", missing: false });
    expect(rows[2]).toMatchObject({ value: "\u2014", missing: true });   // whitespace is missing
    expect(rows[3]).toMatchObject({ value: "false", missing: false });    // a false is a word
    expect(rows[4]).toMatchObject({ value: "\u2014", missing: true });   // absent key
  });
  it("no layer at all -> five dashes, never a throw", () => {
    expect(bearingRows(undefined).every((r) => r.missing)).toBe(true);
  });
});
describe("stopMark", () => {
  it("#196 -- only a \"cut\" marks; a normal stop and an unknown word do not", () => {
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
