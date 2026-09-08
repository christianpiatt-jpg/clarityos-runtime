/**
 * The window declaration, rendered at the surface — one test per panel.
 *
 * ★★★ WHAT THESE PIN (#139). That BOTH analytical panels say what the
 * KERNEL read, from the reply's `_meta` and nothing local; that the panel
 * sends the WHOLE transcript with its message boundaries and the thread
 * surface; that before a reading arrives the line says so with a dash; and
 * that the wording is "last N of M — messages a-b of c" (a tail window),
 * never "first".
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, listThreads: vi.fn(), createThread: vi.fn(), getThread: vi.fn() };
});
vi.mock("../../../lib/elinsV2", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/elinsV2")>("../../../lib/elinsV2");
  return { ...actual, runElinsV2: vi.fn(() => new Promise(() => {})) };
});
vi.mock("../../../lib/emotionalPhysics", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/emotionalPhysics")>(
    "../../../lib/emotionalPhysics",
  );
  return { ...actual, analyzeEmotionalPhysics: vi.fn(() => new Promise(() => {})) };
});

import * as api from "../../../lib/api";
import * as elinsLib from "../../../lib/elinsV2";
import * as physicsLib from "../../../lib/emotionalPhysics";
import ThreadInsightsPanel from "../ThreadInsightsPanel";
import { cockpit } from "../../../state/cockpitStore";
import { composeTranscript, computeBoundaries } from "../../../lib/transcriptWindow";

const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
};

/** The kernel's window for a 44-message, 96,176-char thread read at 12,000. */
const WINDOW = {
  window_anchor: "tail", window_surface: "thread", window_cap: 12000,
  window_chars: 12000, total_chars: 96176, window_coverage: "boundaries",
  window_coverage_reason: null, total_messages: 44, window_messages: 6,
  window_first_message: 38, window_last_message: 44, window_truncated_mid_message: true,
};

const ENVELOPE = {
  elins_version: "elins.v2.0", region: null, input: {}, pipeline: {},
  outputs: {
    collapse_state: "none", attractor: "S1",
    state_distribution: { S1: 1, S2: 0, S3: 0, S4: 0 }, P0_P8: {},
    geography_tier: null, timeline: { short_term_days: 365, mid_term_days: 3650, long_term_days: 18250 },
    multiplier: 1,
  },
  meta: { engine: "clarity_elins_v2", view_kind: "path_c_adapter", warnings: [], notes: [] },
  _meta: WINDOW,
};

const PHYSICS = {
  field_curvature: {}, edge_pressure: {}, relational_primitives: {}, external_expression: {},
  _meta: { model_id: "m", ts_ms: 5, parse_error: null, stop_reason: null, ...WINDOW },
};

/** n messages of `len` content chars each. */
function thread(n: number, len: number) {
  return Array.from({ length: n }, (_, i) => ({
    role: i % 2 === 0 ? "user" : "assistant",
    content: "x".repeat(len),
    ts_ms: 100 + i,
    model: null,
  }));
}

let seq = 0;

/** The cockpit store is a module singleton: a reading cached by the previous
 *  test would stop the view's mount-only auto-run, open() short-circuits on
 *  the thread already selected, and a tab left on ELINS mounts the
 *  declaration before the thread loads (so a node captured early goes
 *  stale). Each mount clears the readings, returns to the thread tab and
 *  opens a fresh thread id. */
async function mount(messages: ReturnType<typeof thread>) {
  const id = `t-${++seq}`;
  vi.mocked(api.listThreads).mockResolvedValue([
    { ...META, thread_id: id, message_count: messages.length },
  ] as never);
  vi.mocked(api.getThread).mockResolvedValue({
    meta: { ...META, thread_id: id, message_count: messages.length },
    messages,
  } as never);
  await act(async () => {
    cockpit.thread.actions.setElins(null);
    cockpit.thread.actions.setPhysics(null);
    cockpit.thread.actions.setTab("thread");
  });
  render(<ThreadInsightsPanel />);
  await act(async () => { await cockpit.thread.actions.init(); });
  await act(async () => { await cockpit.thread.actions.open(id); });
}

/** The declaration as it reads NOW (re-queried, never a captured node). */
const decl = () => screen.getByTestId("window-declaration");

afterEach(() => {
  vi.clearAllMocks();
  vi.mocked(elinsLib.runElinsV2).mockImplementation(() => new Promise(() => {}));
  vi.mocked(physicsLib.analyzeEmotionalPhysics).mockImplementation(() => new Promise(() => {}));
});

describe("ThreadInsightsPanel — the ELINS panel declares the KERNEL's window", () => {
  it("★ sends the whole transcript with its boundaries and the thread surface, then renders _meta", async () => {
    vi.mocked(elinsLib.runElinsV2).mockResolvedValue(ENVELOPE as never);
    const ms = thread(20, 500);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("elins"); });

    // the request: WHOLE transcript, its boundaries, the surface
    await waitFor(() => expect(elinsLib.runElinsV2).toHaveBeenCalled());
    const req = vi.mocked(elinsLib.runElinsV2).mock.calls[0][0];
    expect(req.input.raw_text).toBe(composeTranscript(ms));
    expect(req.input.raw_text.length).toBeGreaterThan(6000);        // nothing sliced
    expect(req.surface).toBe("thread");
    expect(req.message_boundaries).toEqual(computeBoundaries(ms));
    expect(req.message_boundaries?.[19]).toBe(composeTranscript(ms).length);

    // the declaration: the kernel's numbers, a TAIL window
    await waitFor(() => expect(decl()).toHaveTextContent("last 12,000 of 96,176 chars"));
    expect(decl()).toHaveTextContent("messages 38-44 of 44");
    expect(decl()).not.toHaveTextContent("first");
    expect(decl()).toHaveAttribute("title", expect.stringContaining("_meta.window_anchor tail"));
    expect(screen.getByTestId("window-mid-message")).toHaveTextContent("INSIDE message 38");
  });

  it("before a reading arrives the line says so, with a dash — never a local estimate", async () => {
    await mount(thread(20, 500));
    await act(async () => { cockpit.thread.actions.setTab("elins"); });
    await waitFor(() => expect(decl()).toHaveTextContent("read: —"));
    expect(decl()).not.toHaveTextContent("first");
    expect(decl()).not.toHaveTextContent("last");
  });
});

describe("ThreadInsightsPanel — the Physics panel declares the same way", () => {
  it("sends surface + boundaries and renders the reply's _meta", async () => {
    vi.mocked(physicsLib.analyzeEmotionalPhysics).mockResolvedValue(PHYSICS as never);
    const ms = thread(20, 500);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("physics"); });

    await waitFor(() => expect(physicsLib.analyzeEmotionalPhysics).toHaveBeenCalled());
    const req = vi.mocked(physicsLib.analyzeEmotionalPhysics).mock.calls[0][0];
    expect(req.text).toBe(composeTranscript(ms));
    expect(req.surface).toBe("thread");
    expect(req.message_boundaries).toEqual(computeBoundaries(ms));

    await waitFor(() => expect(decl()).toHaveTextContent("read: last 12,000 of 96,176 chars"));
    expect(decl()).toHaveTextContent("of 44");
  });
});

describe("a SHORT thread says it read everything", () => {
  it("renders the kernel's whole-read as 'read: all'", async () => {
    const ms = thread(3, 20);
    const total = composeTranscript(ms).length;
    vi.mocked(elinsLib.runElinsV2).mockResolvedValue({
      ...ENVELOPE,
      _meta: {
        ...WINDOW, window_chars: total, total_chars: total, total_messages: 3, window_messages: 3,
        window_first_message: 1, window_last_message: 3, window_truncated_mid_message: false,
      },
    } as never);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("elins"); });
    await waitFor(() => expect(decl()).toHaveTextContent("read: all"));
    expect(decl()).toHaveTextContent("3 of 3 messages");
    expect(screen.queryByTestId("window-mid-message")).toBeNull();
  });
});

describe("coverage the kernel marked ABSENT renders dashes, never zeros", () => {
  it("chars are declared, messages are dashes", async () => {
    vi.mocked(elinsLib.runElinsV2).mockResolvedValue({
      ...ENVELOPE,
      _meta: {
        ...WINDOW, window_coverage: "ABSENT", window_coverage_reason: "no message boundaries in the request",
        total_messages: null, window_messages: null,
        window_first_message: null, window_last_message: null, window_truncated_mid_message: null,
      },
    } as never);
    await mount(thread(20, 500));
    await act(async () => { cockpit.thread.actions.setTab("elins"); });
    await waitFor(() => expect(decl()).toHaveTextContent("last 12,000 of 96,176 chars"));
    expect(decl()).toHaveTextContent("messages —-— of —");
    // the reason rides beside the dashes, never hidden in a title alone
    expect(screen.getByTestId("window-coverage-reason")).toHaveTextContent("no message boundaries in the request");
    expect(screen.queryByTestId("window-mid-message")).toBeNull();
  });
});

describe("D1 — the rendered declaration MOVES with the kernel's _meta", () => {
  it("two readings with different windows render different text", async () => {
    vi.mocked(elinsLib.runElinsV2).mockResolvedValue(ENVELOPE as never);
    await mount(thread(20, 500));
    await act(async () => { cockpit.thread.actions.setTab("elins"); });
    await waitFor(() => expect(decl()).toHaveTextContent("last 12,000 of 96,176"));
    const small = decl().textContent;

    // a second reading lands (the view's Re-run hands it to the store the
    // same way): the declaration follows its _meta, and nothing else
    await act(async () => {
      cockpit.thread.actions.setElins({
        ...ENVELOPE,
        _meta: {
          ...WINDOW, window_chars: 12000, total_chars: 40000,
          window_first_message: 9, window_last_message: 12, total_messages: 12,
        },
      } as never);
    });
    await waitFor(() => expect(decl()).toHaveTextContent("last 12,000 of 40,000"));
    expect(decl()).toHaveTextContent("messages 9-12 of 12");
    expect(decl().textContent).not.toBe(small);
  });
});
