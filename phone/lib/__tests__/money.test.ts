/** #161 -- dollars on the phone read as they do on the web. */
import { describe, it, expect } from "vitest";
import { microToDollars, fmtDelta, dollarsToMicro } from "../money";

describe("money (the web's lib/money, verbatim)", () => {
  it("\u2605 661054 -> $0.66 · 900 -> $0.00 · null -> —", () => {
    expect(microToDollars(661054)).toBe("$0.66");
    expect(microToDollars(900)).toBe("$0.00");
    expect(microToDollars(null)).toBe("\u2014");
    expect(microToDollars(undefined)).toBe("\u2014");
    expect(microToDollars(-1_000_000)).toBe("-$1.00");
  });
  it("a delta is signed; a sub-cent delta is $0.00 with no sign", () => {
    expect(fmtDelta(15_000_000)).toBe("+$15.00");
    expect(fmtDelta(-1_000_000)).toBe("-$1.00");
    expect(fmtDelta(900)).toBe("$0.00");
    expect(fmtDelta(null)).toBe("\u2014");
  });
  it("typed dollars -> micro on the cent grid", () => {
    expect(dollarsToMicro("15.00")).toBe(15_000_000);
    expect(dollarsToMicro("-2.50")).toBe(-2_500_000);
    expect(dollarsToMicro("1.005")).toBeNull();
  });
});
