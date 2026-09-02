/**
 * The window declaration, rendered at the surface — one test per panel.
 *
 * ★★★ WHAT THESE PIN. That BOTH analytical panels say what they read, and
 * that the numbers they show are the numbers actually sent. Before this,
 * a 10-message thread was analysed from its first 6,000 characters — 17%
 * of it, ending inside message 3 — and the panel reported the result with
 * no indication that messages 4-10 had never been read.
 *
 * ★★ The declaration does not change the window. Same cap, same head
 * anchor, same content. These tests would pass just as well against a tail
 * window or a larger one; what they refuse is a panel that stays silent.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

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
import ThreadInsightsPanel from "../ThreadInsightsPanel";
import { cockpit } from "../../../state/cockpitStore";
import { composeTranscript } from "../../../lib/transcriptWindow";

const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
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

async function mount(messages: ReturnType<typeof thread>) {
  vi.mocked(api.listThreads).mockResolvedValue([
    { ...META, message_count: messages.length },
  ] as never);
  vi.mocked(api.getThread).mockResolvedValue({
    meta: { ...META, message_count: messages.length },
    messages,
  } as never);
  render(<ThreadInsightsPanel />);
  await act(async () => { await cockpit.thread.actions.init(); });
}

afterEach(() => vi.clearAllMocks());

describe("ThreadInsightsPanel — the ELINS panel declares its window", () => {
  it("a LONG thread reports a partial read, with the numbers actually sent", async () => {
    const ms = thread(20, 500);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("elins"); });

    const decl = await screen.findByTestId("window-declaration");
    // ★ The character count on screen must be the length of the string
    // handed to the request — not the cap, and not an estimate.
    expect(decl).toHaveTextContent(
      `first ${composeTranscript(ms).length.toLocaleString()}`,
    );
    expect(decl).toHaveTextContent("of 20");
    // 20 x ~511 chars is far past the cap, so the cut lands mid-message.
    expect(screen.getByTestId("window-mid-message")).toBeInTheDocument();
  });
});

describe("ThreadInsightsPanel — the Physics panel declares the same window", () => {
  it("renders the declaration on the physics tab too", async () => {
    const ms = thread(20, 500);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("physics"); });

    const decl = await screen.findByTestId("window-declaration");
    expect(decl).toHaveTextContent("read: first");
    expect(decl).toHaveTextContent("of 20");
  });
});

describe("a SHORT thread says it read everything", () => {
  it("reports the whole thread and flags no mid-message cut", async () => {
    const ms = thread(3, 20);
    await mount(ms);
    await act(async () => { cockpit.thread.actions.setTab("elins"); });

    const decl = await screen.findByTestId("window-declaration");
    expect(decl).toHaveTextContent("read: all");
    expect(decl).toHaveTextContent("3 of 3 messages");
    expect(screen.queryByTestId("window-mid-message")).toBeNull();
  });
});

describe("D1 — the rendered declaration MOVES", () => {
  it("a short and a long thread render different text", async () => {
    await mount(thread(3, 20));
    await act(async () => { cockpit.thread.actions.setTab("elins"); });
    const small = (await screen.findByTestId("window-declaration")).textContent;

    // ★ A DIFFERENT thread_id: open() short-circuits on the one already
    // selected (cockpitStore.ts:596), which silently made both reads the
    // same render and cost this test one false pass.
    vi.mocked(api.getThread).mockResolvedValue({
      meta: { ...META, thread_id: "t2", message_count: 30 },
      messages: thread(30, 500),
    } as never);
    await act(async () => { await cockpit.thread.actions.open("t2"); });
    const large = (await screen.findByTestId("window-declaration")).textContent;

    // ★ A static ratio would mean a constant is being rendered.
    expect(small).not.toBe(large);
  });
});
