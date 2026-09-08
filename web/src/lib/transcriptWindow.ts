// transcriptWindow — what the instrument actually read.
//
// ★★★ THE KERNEL CUTS. THE BROWSER DECLARES. (#139, CT-1 ruled 2026-09-03)
// Anchor = TAIL on every surface; size = 6,000 for Personal ELINS
// (relational turns weigh more), 12,000 everywhere else. This file no
// longer slices anything: the panel sends the WHOLE composed transcript
// plus the message boundaries it computed over that exact string, and the
// kernel answers with the window it read in `_meta`. The declaration line
// renders `_meta` unchanged — never a local estimate of what the kernel
// might have done.
//
// WHY IT EXISTS
// A panel that renders a reading without saying what it read is reporting
// over a set it never received. Measured 2026-09-02: a 10-message,
// 35,334-character thread was analysed from its first 6,000 characters —
// 17.0% of the thread, ending INSIDE message 3. The declaration (09-02)
// made that visible; the ruling (09-03) moved the cut to the tail and to
// the kernel; this file now carries only the two things the browser still
// owns: the composed string and its boundaries.
//
// ★★ Three constants used to describe one window and two of them lied by
// omission (this file's 6,000 head slice, the kernel's 6,000 head cut, no
// cap at all on /elins/v2/run). There is one now, and it is the kernel's.

export interface TranscriptMessage {
  role: string;
  content: string;
}

/** The kernel's window facts, as `_meta` carries them (intelligence_kernel
 *  cut_window). Every field is what the KERNEL read; nothing here is
 *  computed in the browser. Coverage fields are null when the kernel had
 *  no boundaries to count with (window_coverage "ABSENT"). */
export interface WindowMeta {
  window_anchor?: "tail" | "head" | string;
  window_surface?: "personal" | "thread" | string;
  window_cap?: number;
  window_chars?: number;
  total_chars?: number;
  window_coverage?: "boundaries" | "ABSENT" | string;
  window_coverage_reason?: string | null;
  total_messages?: number | null;
  window_messages?: number | null;
  window_first_message?: number | null;
  window_last_message?: number | null;
  window_truncated_mid_message?: boolean | null;
}

/** The window facts the declaration renders. Numbers come from `_meta`;
 *  a null coverage number renders as a dash, never as a guess. */
export interface TranscriptWindow {
  /** Characters the kernel actually read. */
  window_chars: number;
  /** Characters in the full composed transcript, as the kernel measured it. */
  total_chars: number;
  /** Which end the window is anchored to. The ruling says tail; rendered as sent. */
  window_anchor: string;
  /** Which surface sized the window. */
  window_surface: string;
  /** WHOLE messages inside the window, or null when the kernel had no boundaries. */
  window_messages: number | null;
  /** 1-based index of the first message the window touches, or null. */
  window_first_message: number | null;
  /** 1-based index of the last message the window touches, or null. */
  window_last_message: number | null;
  /** Messages in the thread, as the boundaries said, or null. */
  total_messages: number | null;
  /** True when the cut lands inside a message: with a TAIL anchor the reading
   *  opens on a fragment whose own beginning it never saw. Null when unknown. */
  window_truncated_mid_message: boolean | null;
  /** Why the coverage numbers are null, when they are; null otherwise. */
  window_coverage_reason: string | null;
}

/** Compose the transcript exactly as the panels send it: role-prefixed
 *  lines joined with "\n". NO slice, NO trim — the boundaries below are
 *  offsets into this exact string, and the kernel checks that the last
 *  boundary equals the length it received; a trimmed string would make
 *  every count wrong by the trimmed amount. */
export function composeTranscript(messages: TranscriptMessage[]): string {
  return messages.map((m) => `${m.role}: ${m.content}`).join("\n");
}

/** Length in CODE POINTS, the unit the kernel measures in (Python len).
 *  A JS `.length` is UTF-16 code units and counts every emoji twice; the
 *  kernel checks that the last boundary equals the length it received, so
 *  one emoji in a thread would turn the whole thread's coverage ABSENT. */
export function codePoints(s: string): number {
  return Array.from(s).length;
}

/** The last `n` CODE POINTS of `s` -- the kernel's tail cut, reproduced on
 *  the same unit, so a caller can hand on exactly the text a run read. */
export function tailByCodePoints(s: string, n: number): string {
  const cps = Array.from(s);
  return n >= cps.length ? s : cps.slice(cps.length - n).join("");
}

/** Cumulative END offset (in code points) of each message inside
 *  composeTranscript(messages): the parts plus the "\n" separators that
 *  precede them. The last entry is the string's code-point length. Sent with
 *  the request so the kernel can say which messages its window covers
 *  without re-deriving them. */
export function computeBoundaries(messages: TranscriptMessage[]): number[] {
  let cum = 0;
  const boundaries: number[] = [];
  messages.forEach((m, i) => {
    cum += (i === 0 ? 0 : 1) + codePoints(`${m.role}: ${m.content}`);
    boundaries.push(cum);
  });
  return boundaries;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** The window facts from a response's `_meta`, or null when the response
 *  carries none (no reading yet, or a kernel that predates the stamp). The
 *  numbers are rendered as the kernel sent them. */
export function windowFromMeta(raw: unknown): TranscriptWindow | null {
  if (!raw || typeof raw !== "object") return null;
  const meta = raw as WindowMeta;
  const window_chars = num(meta.window_chars);
  const total_chars = num(meta.total_chars);
  if (window_chars === null || total_chars === null) return null;
  return {
    window_chars,
    total_chars,
    window_anchor: typeof meta.window_anchor === "string" ? meta.window_anchor : "—",
    window_surface: typeof meta.window_surface === "string" ? meta.window_surface : "—",
    window_messages: num(meta.window_messages),
    window_first_message: num(meta.window_first_message),
    window_last_message: num(meta.window_last_message),
    total_messages: num(meta.total_messages),
    window_truncated_mid_message:
      typeof meta.window_truncated_mid_message === "boolean" ? meta.window_truncated_mid_message : null,
    window_coverage_reason:
      typeof meta.window_coverage_reason === "string" && meta.window_coverage_reason
        ? meta.window_coverage_reason : null,
  };
}
