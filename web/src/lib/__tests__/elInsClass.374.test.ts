/**
 * #374 -- the EL/INS classification's word and colour, in ONE place.
 *
 * ★ WHY THIS FILE EXISTS. Four routes carried a byte-identical private
 * `classColor`, and three of the four fell through to the OK green for any
 * value they did not recognise. When #355 put a fourth value on the wire --
 * "UNMAPPED", meaning the run carried NO reading -- those three rendered it
 * in the colour of a healthy balanced one. Absence, painted as health.
 *
 * Every test below names the mutation that breaks it. A test that cannot
 * name one does not belong here: the #355 build shipped six tautologies and
 * each was caught by a refuter or a mutation run rather than by a test.
 */
import { describe, it, expect } from "vitest";

import {
  DASH,
  EL_INS_UNMAPPED,
  elInsClassColor,
  elInsClassWord,
} from "../labels";

describe("#374 -- elInsClassWord", () => {
  it("★ renders UNMAPPED as an em dash, not as the word", () => {
    // MUTATION: return `cls` unchanged for UNMAPPED.
    // A member reading "UNMAPPED" in a table learns an internal token; a
    // member reading "—" learns there is nothing there, which is the fact.
    expect(elInsClassWord(EL_INS_UNMAPPED)).toBe(DASH);
    expect(elInsClassWord(EL_INS_UNMAPPED)).not.toBe("UNMAPPED");
  });

  it("passes the three real classes through untouched", () => {
    // MUTATION: dash everything. The guard must not be a blanket off-switch
    // -- #374 names an absence, it does not delete the readings.
    expect(elInsClassWord("balanced")).toBe("balanced");
    expect(elInsClassWord("high_el")).toBe("high_el");
    expect(elInsClassWord("high_ins")).toBe("high_ins");
  });

  it("never returns blank for null, undefined or empty", () => {
    // MUTATION: `return cls ?? ""`.
    for (const v of [null, undefined, ""]) {
      expect(elInsClassWord(v as string | null | undefined)).toBe(DASH);
    }
  });

  it("returns an unknown value as itself rather than hiding it", () => {
    // MUTATION: dash the default. A value this table has not heard of is
    // information; swallowing it is how a fifth wire state would go unseen.
    expect(elInsClassWord("some_future_state")).toBe("some_future_state");
  });
});

describe("#374 -- elInsClassColor", () => {
  it("★ UNMAPPED is muted, and is NOT the balanced colour", () => {
    // MUTATION: drop the explicit `balanced` arm, or make the default green.
    // This is the defect in one assertion: three of the four private copies
    // returned --os-ok for UNMAPPED, i.e. the same green as a healthy read.
    const unmapped = elInsClassColor(EL_INS_UNMAPPED);
    expect(unmapped).toContain("--os-text-muted");
    expect(unmapped).not.toBe(elInsClassColor("balanced"));
  });

  it("★ the DEFAULT is muted, not green -- an unheard-of value is not health", () => {
    // MUTATION: `return "var(--os-ok, #10b981)"` as the fallback, which is
    // exactly what the three private copies did.
    expect(elInsClassColor("a_state_from_the_future")).toContain("--os-text-muted");
    expect(elInsClassColor(null)).toContain("--os-text-muted");
  });

  it("the three real classes keep their existing colours", () => {
    // MUTATION: any re-colouring. These are pinned so #374 is provably a
    // pure addition for every value that already had a meaning.
    expect(elInsClassColor("high_el")).toContain("--os-err");
    expect(elInsClassColor("high_ins")).toContain("--os-warn");
    expect(elInsClassColor("balanced")).toContain("--os-ok");
  });

  it("★ all four states resolve to four distinct colours", () => {
    // MUTATION: collapse any two arms. If two states share a colour the
    // surface cannot distinguish them, which is the #355 defect in pixels.
    const seen = new Set(
      ["high_el", "high_ins", "balanced", EL_INS_UNMAPPED].map(elInsClassColor),
    );
    expect(seen.size).toBe(4);
  });
});
