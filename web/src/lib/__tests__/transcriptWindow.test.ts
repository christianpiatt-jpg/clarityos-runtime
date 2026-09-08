/**
 * The window — what the browser still owns, and what it renders unchanged.
 *
 * ★★★ WHAT THESE PIN (#139). The browser no longer slices: composeTranscript
 * is the whole join, computeBoundaries are the end offsets over that exact
 * string (the kernel checks the last one equals the length it received),
 * and windowFromMeta renders the kernel's `_meta` numbers as sent — never a
 * local estimate. A missing `_meta` is null, so the panel can say "no
 * reading yet" instead of guessing.
 */
import { describe, it, expect } from "vitest";

import {
  codePoints,
  composeTranscript,
  computeBoundaries,
  tailByCodePoints,
  windowFromMeta,
} from "../transcriptWindow";

const msg = (role: string, content: string) => ({ role, content });

/** n messages of `len` content characters each. */
function thread(n: number, len: number) {
  return Array.from({ length: n }, (_, i) =>
    msg(i % 2 === 0 ? "user" : "assistant", "x".repeat(len)),
  );
}

describe("composeTranscript — the whole transcript, no slice, no trim", () => {
  it("is the role-prefixed join and nothing shorter", () => {
    const ms = thread(5, 40);
    const inline = ms.map((m) => `${m.role}: ${m.content}`).join("\n");
    expect(composeTranscript(ms)).toBe(inline);
  });

  it("★ a 40 x 500 thread is sent WHOLE — the 6,000 slice is gone", () => {
    const ms = thread(40, 500);
    const sent = composeTranscript(ms);
    expect(sent.length).toBeGreaterThan(6000);
    // exactly: each part is "<role>: " + 500 chars, joined by 39 newlines
    const exact = ms.reduce((n, m) => n + `${m.role}: `.length + 500, 0) + 39;
    expect(sent.length).toBe(exact);
  });

  it("keeps trailing whitespace, so the boundaries stay true to the bytes sent", () => {
    const ms = [msg("user", "hello "), msg("assistant", " hi ")];
    const sent = composeTranscript(ms);
    expect(sent.endsWith(" ")).toBe(true);
    expect(computeBoundaries(ms)[1]).toBe(sent.length);
  });
});

describe("computeBoundaries — cumulative END offsets over the sent string", () => {
  it("the last boundary is the length of composeTranscript", () => {
    const ms = thread(20, 500);
    const b = computeBoundaries(ms);
    expect(b.length).toBe(20);
    expect(b[b.length - 1]).toBe(composeTranscript(ms).length);
  });

  it("each boundary is the end of its message inside the join", () => {
    const ms = [msg("user", "aaaa"), msg("assistant", "bbbb")];
    // "user: aaaa" = 10, "\n" + "assistant: bbbb" = 1 + 15
    expect(computeBoundaries(ms)).toEqual([10, 26]);
    const sent = composeTranscript(ms);
    expect(sent.slice(0, 10)).toBe("user: aaaa");
    expect(sent.slice(11, 26)).toBe("assistant: bbbb");
  });

  it("is strictly increasing", () => {
    const b = computeBoundaries(thread(30, 7));
    for (let i = 1; i < b.length; i++) expect(b[i]).toBeGreaterThan(b[i - 1]);
  });

  it("an empty thread has no boundaries", () => {
    expect(computeBoundaries([])).toEqual([]);
    expect(composeTranscript([])).toBe("");
  });

  it("★ counts CODE POINTS, the kernel's unit -- an emoji is one, not two", () => {
    const ms = [msg("user", "hi 😀"), msg("assistant", "ok 👍")];
    // "user: hi 😀" = 10 code points but 11 UTF-16 units
    expect("user: hi 😀".length).toBe(11);
    expect(codePoints("user: hi 😀")).toBe(10);
    expect(computeBoundaries(ms)).toEqual([10, 10 + 1 + codePoints("assistant: ok 👍")]);
    expect(computeBoundaries(ms)[1]).toBe(codePoints(composeTranscript(ms)));
  });
});

describe("tailByCodePoints — the kernel's cut, on the same unit", () => {
  it("keeps the last n code points, whole emoji included", () => {
    expect(tailByCodePoints("abc😀def", 4)).toBe("😀def");
    expect(tailByCodePoints("abc😀def", 3)).toBe("def");
    expect(tailByCodePoints("abc", 10)).toBe("abc");
  });
});

describe("windowFromMeta — the kernel's numbers, rendered unchanged", () => {
  const META = {
    window_anchor: "tail", window_surface: "thread", window_cap: 12000,
    window_chars: 12000, total_chars: 96176, window_coverage: "boundaries",
    window_coverage_reason: null, total_messages: 44, window_messages: 6,
    window_first_message: 38, window_last_message: 44, window_truncated_mid_message: true,
  };

  it("★ carries every number as sent", () => {
    const w = windowFromMeta(META);
    expect(w).toEqual({
      window_chars: 12000, total_chars: 96176, window_anchor: "tail", window_surface: "thread",
      window_messages: 6, window_first_message: 38, window_last_message: 44,
      total_messages: 44, window_truncated_mid_message: true, window_coverage_reason: null,
    });
  });

  it("no _meta, or a _meta without the window, is null — not a guess", () => {
    expect(windowFromMeta(undefined)).toBeNull();
    expect(windowFromMeta(null)).toBeNull();
    expect(windowFromMeta({ model_id: "x", ts_ms: 1 })).toBeNull();
    expect(windowFromMeta("12000")).toBeNull();
  });

  it("coverage the kernel marked ABSENT reads null, never zero", () => {
    const w = windowFromMeta({
      ...META, window_coverage: "ABSENT", window_coverage_reason: "no message boundaries in the request",
      total_messages: null, window_messages: null,
      window_first_message: null, window_last_message: null, window_truncated_mid_message: null,
    });
    expect(w?.window_coverage_reason).toBe("no message boundaries in the request");
    expect(w?.window_messages).toBeNull();
    expect(w?.window_first_message).toBeNull();
    expect(w?.window_truncated_mid_message).toBeNull();
    expect(w?.window_chars).toBe(12000);
  });

  it("D1 — two different _meta render two different windows", () => {
    const a = windowFromMeta(META);
    const b = windowFromMeta({ ...META, window_chars: 6000, window_surface: "personal", window_first_message: 41 });
    expect(a).not.toEqual(b);
    expect(b?.window_chars).toBe(6000);
  });
});
