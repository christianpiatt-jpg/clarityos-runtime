/**
 * #161a -- the live sha is read once per boot, shared across screens.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { liveShaOnce, _resetLiveShaForTests } from "../liveSha";

describe("#161a -- the live sha is read once per boot", () => {
  beforeEach(() => _resetLiveShaForTests());

  it("★ two screens, one /health read: the in-flight read is shared and the cache answers after it", async () => {
    let calls = 0;
    const fetcher = async () => { calls += 1; return { commit_sha: "ABCDEF1234567" }; };
    const [a, b] = await Promise.all([liveShaOnce(fetcher), liveShaOnce(fetcher)]);
    expect(a).toBe("abcdef1234567");
    expect(b).toBe(a);
    expect(calls).toBe(1);
    expect(await liveShaOnce(fetcher)).toBe(a);
    expect(calls).toBe(1);
  });

  it("'unknown' and an unreachable backend both read null -- never a false current, and not re-asked", async () => {
    expect(await liveShaOnce(async () => ({ commit_sha: "unknown" }))).toBeNull();
    _resetLiveShaForTests();
    let calls = 0;
    const down = async () => { calls += 1; throw new Error("down"); };
    expect(await liveShaOnce(down)).toBeNull();
    expect(await liveShaOnce(down)).toBeNull();
    expect(calls).toBe(1);
  });
});
