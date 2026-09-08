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
  it("end_turn / absent -> null; anything else -> its word", () => {
    expect(stopMark("end_turn")).toBeNull();
    expect(stopMark(null)).toBeNull();
    expect(stopMark("max_tokens")).toBe("max_tokens");
  });
});
