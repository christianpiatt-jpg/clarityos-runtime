/**
 * #142 -- dollars at $0.01, floored; deltas signed; the console's dollars
 * become micro on the wire. #171 -- the three words.
 */
import { describe, it, expect } from "vitest";
import { microToDollars, fmtDelta, dollarsToMicro } from "../money";
import { cohortWord } from "../cohortWord";

describe("money", () => {
  it("floors to the cent", () => {
    expect(microToDollars(661054)).toBe("$0.66");
    expect(microToDollars(900)).toBe("$0.00");
    expect(microToDollars(1_000_000)).toBe("$1.00");
    expect(microToDollars(15_000_000)).toBe("$15.00");
    expect(microToDollars(-1_000_000)).toBe("-$1.00");
    expect(microToDollars(-900)).toBe("$0.00");   // no sign on nothing
    expect(microToDollars(undefined)).toBe("\u2014");
  });
  it("signs a delta; a sub-cent delta is $0.00 with no sign", () => {
    expect(fmtDelta(1_000_000)).toBe("+$1.00");
    expect(fmtDelta(15_000_000)).toBe("+$15.00");
    expect(fmtDelta(-1_000_000)).toBe("-$1.00");
    expect(fmtDelta(900)).toBe("$0.00");
    expect(fmtDelta(-900)).toBe("$0.00");
  });
  it("dollars typed at $0.01 become micro; anything else is refused", () => {
    expect(dollarsToMicro("15.00")).toBe(15_000_000);
    expect(dollarsToMicro("15")).toBe(15_000_000);
    expect(dollarsToMicro("-2.50")).toBe(-2_500_000);
    expect(dollarsToMicro("0.01")).toBe(10_000);
    expect(dollarsToMicro("1.005")).toBeNull();
    expect(dollarsToMicro("abc")).toBeNull();
    expect(dollarsToMicro("")).toBeNull();
  });
});

describe("cohortWord (#171)", () => {
  it("admin for a controller, citizen for a numbered member, a dash otherwise", () => {
    expect(cohortWord({ member_number: 1, controller: true })).toBe("admin");
    expect(cohortWord({ member_number: 7, controller: false })).toBe("citizen");
    expect(cohortWord({ member_number: null, controller: false })).toBe("\u2014");
    expect(cohortWord({})).toBe("\u2014");
    expect(cohortWord(null)).toBe("\u2014");
  });
});
