// transcriptWindow — what the instrument actually read.
//
// ★★★ THIS FILE DECLARES A WINDOW. IT DOES NOT CHANGE ONE.
// The 6,000-character cap, its head anchor, and its content are exactly
// what they were. Every number here describes the slice that is already
// being sent; nothing here alters what is sent. If the window is wrong —
// and it may well be — that is a separate ruling and a separate change.
//
// WHY IT EXISTS
// A panel that renders a reading without saying what it read is reporting
// over a set it never received. Measured 2026-09-02: a 10-message,
// 35,334-character thread was analysed from its first 6,000 characters —
// 17.0% of the thread, ending INSIDE message 3. Messages 4-10 had never
// been read, including both emotional-physics exchanges. The panel said
// nothing about any of that.
//
// ★★ This is the shadow layer's own discipline applied to a window instead
// of a value: state what was measured, state what was not, and never let
// an absence look like a reading.

/** The client-side cap. Mirrors intelligence_kernel's own input cap; the
 *  transcript is sliced here, before the request leaves the browser. */
export const TRANSCRIPT_CHAR_CAP = 6000;

export interface TranscriptMessage {
  role: string;
  content: string;
}

/** The window facts for one composed transcript. */
export interface TranscriptWindow {
  /** Characters actually sent. */
  window_chars: number;
  /** WHOLE messages the window covers. */
  window_messages: number;
  /** Messages in the thread. */
  total_messages: number;
  /** Characters in the full composed transcript. */
  total_chars: number;
  /** Which end the window is anchored to. Stated as it IS today. */
  window_anchor: "head" | "tail";
  /** True when the cut lands inside a message rather than on a boundary. */
  window_truncated_mid_message: boolean;
}

/** Compose the transcript exactly as the panels already do.
 *
 *  ★ BYTE-IDENTICAL to the inline expression it replaces
 *  (ThreadInsightsPanel.tsx, and the still-inline twin at Threads.tsx:326):
 *  join with "\n", slice from the head, then trim. The trim can shorten the
 *  result below the cap, which is why `window_chars` is measured from the
 *  composed output rather than assumed to equal the cap.
 */
export function composeTranscript(
  messages: TranscriptMessage[],
  cap: number = TRANSCRIPT_CHAR_CAP,
): string {
  return messages
    .map((m) => `${m.role}: ${m.content}`)
    .join("\n")
    .slice(0, cap)
    .trim();
}

/** Describe what the composed transcript covers.
 *
 *  ★ Message boundaries ARE determinable here: the panel holds the whole
 *  `messages` array, so `window_messages` is counted, never estimated. If a
 *  caller ever lacks the array, the honest return is a sentinel — not a
 *  guess — but that case does not arise on this surface.
 */
export function computeWindow(
  messages: TranscriptMessage[],
  cap: number = TRANSCRIPT_CHAR_CAP,
): TranscriptWindow {
  const parts = messages.map((m) => `${m.role}: ${m.content}`);
  const full = parts.join("\n");
  const sent = composeTranscript(messages, cap);
  const window_chars = sent.length;

  // Cumulative end offset of each message inside `full`: the parts plus the
  // "\n" separators that precede them.
  let cum = 0;
  const boundaries: number[] = [];
  parts.forEach((p, i) => {
    cum += (i === 0 ? 0 : 1) + p.length;
    boundaries.push(cum);
  });

  const window_messages = boundaries.filter((b) => b <= window_chars).length;
  const covers_everything = window_chars >= full.length;

  return {
    window_chars,
    window_messages,
    total_messages: messages.length,
    total_chars: full.length,
    // The slice is `.slice(0, cap)` — it keeps the FIRST characters. Stated
    // as measured, not as preferred. A tail anchor would report "tail".
    window_anchor: "head",
    // ★★★ A window that cuts a message in half is a different fact from one
    // that lands on a boundary: the reading then contains a fragment whose
    // own ending it never saw.
    window_truncated_mid_message:
      !covers_everything && !boundaries.includes(window_chars),
  };
}
