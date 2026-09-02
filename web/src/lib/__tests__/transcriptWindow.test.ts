/**
 * The window declaration — what the insight panels actually read.
 *
 * ★★★ WHAT THESE PIN. Not the window. The window is unchanged and this
 * order does not rule on it. They pin that the DECLARATION IS A
 * MEASUREMENT: a 3-message thread and a 30-message thread must report
 * different numbers, and those numbers must be arithmetically consistent
 * with the payload actually sent. A static ratio would mean the panel is
 * rendering a constant dressed as a reading.
 *
 * ★★ They also pin the mid-message flag, because a window that cuts a
 * message in half is a different fact from one landing on a boundary: the
 * reading then contains a fragment whose own ending it never saw.
 */
import { describe, it, expect } from "vitest";

import {
  TRANSCRIPT_CHAR_CAP,
  composeTranscript,
  computeWindow,
} from "../transcriptWindow";

const msg = (role: string, content: string) => ({ role, content });

/** n messages of `len` content characters each. */
function thread(n: number, len: number) {
  return Array.from({ length: n }, (_, i) =>
    msg(i % 2 === 0 ? "user" : "assistant", "x".repeat(len)),
  );
}

describe("composeTranscript", () => {
  it("is byte-identical to the inline expression it replaced", () => {
    const ms = thread(5, 40);
    const inline = ms
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n")
      .slice(0, 6000)
      .trim();
    expect(composeTranscript(ms)).toBe(inline);
  });

  it("caps at the same 6,000 characters that reach the wire", () => {
    // Measured 2026-09-02: the HAR shows raw_text arriving at EXACTLY 6000.
    expect(TRANSCRIPT_CHAR_CAP).toBe(6000);
    expect(composeTranscript(thread(40, 500)).length).toBe(6000);
  });
});

describe("computeWindow — a SHORT thread", () => {
  const ms = [msg("user", "hello"), msg("assistant", "hi there")];
  const w = computeWindow(ms);

  it("reports the window as the whole thread", () => {
    expect(w.window_chars).toBe(w.total_chars);
    expect(w.window_messages).toBe(w.total_messages);
    expect(w.total_messages).toBe(2);
  });

  it("does not claim a mid-message cut when nothing was cut", () => {
    expect(w.window_truncated_mid_message).toBe(false);
  });
});

describe("computeWindow — a LONG thread", () => {
  // 20 messages x 500 chars: far past the cap, and the cut lands mid-message.
  const ms = thread(20, 500);
  const w = computeWindow(ms);

  it("reports less than the whole thread", () => {
    expect(w.window_chars).toBeLessThan(w.total_chars);
    expect(w.window_messages).toBeLessThan(w.total_messages);
    expect(w.total_messages).toBe(20);
  });

  it("is arithmetically consistent with the payload actually sent", () => {
    // ★ THE LOAD-BEARING ASSERTION. The declared character count must equal
    // the length of the string that is handed to the request, not the cap
    // and not an estimate.
    expect(w.window_chars).toBe(composeTranscript(ms).length);
  });

  it("counts WHOLE messages only, never a partial one", () => {
    const parts = ms.map((m) => `${m.role}: ${m.content}`);
    let cum = 0;
    let whole = 0;
    parts.forEach((p, i) => {
      cum += (i === 0 ? 0 : 1) + p.length;
      if (cum <= w.window_chars) whole += 1;
    });
    expect(w.window_messages).toBe(whole);
  });

  it("flags that the cut lands inside a message", () => {
    expect(w.window_truncated_mid_message).toBe(true);
  });
});

describe("D1 — the declaration MOVES", () => {
  it("a 3-message and a 30-message thread report different numbers", () => {
    const small = computeWindow(thread(3, 500));
    const large = computeWindow(thread(30, 500));
    expect(small.total_messages).not.toBe(large.total_messages);
    expect(small.total_chars).not.toBe(large.total_chars);
    // ★ A static ratio would mean a constant is being rendered.
    const ratio = (w: { window_chars: number; total_chars: number }) =>
      w.window_chars / w.total_chars;
    expect(ratio(small)).not.toBeCloseTo(ratio(large), 3);
  });

  it("coverage falls as the thread grows past the cap", () => {
    const a = computeWindow(thread(10, 500));
    const b = computeWindow(thread(40, 500));
    expect(a.window_chars / a.total_chars).toBeGreaterThan(
      b.window_chars / b.total_chars,
    );
  });
});

describe("the anchor is stated as measured", () => {
  it("reports head, because the slice keeps the FIRST characters", () => {
    const w = computeWindow(thread(20, 500));
    expect(w.window_anchor).toBe("head");
    // And the evidence: the sent text starts with message 1.
    expect(composeTranscript(thread(20, 500)).startsWith("user: ")).toBe(true);
  });
});

describe("a boundary-aligned cut is NOT reported as mid-message", () => {
  it("lands exactly on a message end", () => {
    // "user: aaaa" is 10 chars; a cap of 10 ends exactly at that boundary.
    const ms = [msg("user", "aaaa"), msg("assistant", "bbbb")];
    const w = computeWindow(ms, 10);
    expect(w.window_chars).toBe(10);
    expect(w.window_messages).toBe(1);
    expect(w.window_truncated_mid_message).toBe(false);
  });
});
