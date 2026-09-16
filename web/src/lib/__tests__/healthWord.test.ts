/** #151 -- the probe word, shared with the phone (phone/lib/wire.ts). */
import { describe, it, expect } from "vitest";
import { healthWord } from "../healthWord";

describe("#151 -- the health probe's word", () => {
  it("★ 401 / 403 are the two auth words; another status names itself; none is unreachable; never a server string", () => {
    expect(healthWord(401)).toBe("not signed in");
    expect(healthWord(403)).toBe("not permitted");
    expect(healthWord(500)).toBe("HTTP 500");
    expect(healthWord(404)).toBe("HTTP 404");
    expect(healthWord(0)).toBe("unreachable");
    expect(healthWord(undefined)).toBe("unreachable");
    expect(healthWord("Internal Server Error")).toBe("unreachable");
  });
});
