/**
 * Threads reads newest-first, with the composer at the top.
 *
 * ★★ THE FOUR MOVES TRAVEL TOGETHER. Inverting the list alone would open
 * every thread on its OLDEST message — a worse scroll, arrived at by fixing
 * the scroll. So these assert the ORDER, the absence of the scroll chase,
 * and the composer's position together.
 *
 * ★ The scroll machinery was DELETED, not repointed: with newest-first and
 * the composer at the top, the newest message and the input both sit at
 * scroll position zero. There is nothing to scroll to.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    getThread: vi.fn(),
    postThreadMessage: vi.fn(),
    createThread: vi.fn(),
    renameThread: vi.fn(),
    deleteThread: vi.fn(),
    summarizeThread: vi.fn(),
  };
});
vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  const snap = { session: "s", user: "u@example.com", profile: { cohort: "member" } };
  return { ...actual, getAuthSnapshot: () => snap, subscribeAuth: () => () => {} };
});
// The insight views fire their own requests; stand them down.
vi.mock("../../components/v1/ElinsV2View/ElinsV2View", () => ({ default: () => null }));
vi.mock("../../components/v1/EmotionalPhysicsView/EmotionalPhysicsView", () => ({ default: () => null }));

import * as api from "../../lib/api";
import Threads from "../Threads";

const META = {
  thread_id: "t1", title: "T", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
};

function msgs(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    role: i % 2 === 0 ? "user" : "assistant",
    content: `message ${i + 1}`,
    ts_ms: 1000 + i,
    model: null,
  }));
}

/** Render AND open the thread. Threads shows the list until one is
 *  selected — the existing suite drives it the same way
 *  (Threads.test.tsx:149). */
async function mount() {
  const user = userEvent.setup();
  const r = render(<MemoryRouter><Threads /></MemoryRouter>);
  await screen.findByText("T");
  await user.click(screen.getByRole("button", { name: /Open thread T/i }));
  return r;
}

beforeEach(() => {
  vi.mocked(api.listThreads).mockResolvedValue([META] as never);
});
afterEach(() => vi.clearAllMocks());

describe("Threads — inverted reading order", () => {
  it("★ GATE 4: with 8 messages the NEWEST renders first, oldest last", async () => {
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: { ...META, message_count: 8 }, messages: msgs(8) } as never,
    );
    await mount();
    await screen.findByText("message 8");

    const bodies = screen.getAllByText(/^message \d+$/).map((n) => n.textContent);
    expect(bodies[0]).toBe("message 8");
    expect(bodies[bodies.length - 1]).toBe("message 1");
  });

  it("the scroll chase is gone — nothing calls scrollIntoView", async () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: { ...META, message_count: 8 }, messages: msgs(8) } as never,
    );
    await mount();
    await screen.findByText("message 8");
    // Repointing it to scroll-to-top would fire a scroll to where the
    // browser already is. It was removed instead.
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("★ the composer renders ABOVE the message log", async () => {
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: { ...META, message_count: 8 }, messages: msgs(8) } as never,
    );
    const { container } = await mount();
    await screen.findByText("message 8");

    const composer = screen.getByLabelText("Compose message");
    const newest = screen.getByText("message 8");
    // DOCUMENT_POSITION_FOLLOWING === 4: newest comes AFTER the composer.
    expect(composer.compareDocumentPosition(newest) & 4).toBeTruthy();
    expect(container).toBeTruthy();
  });

  it("★ NEGATIVE CONTROL: a ONE-message thread renders it, with no empty region", async () => {
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: { ...META, message_count: 1 }, messages: msgs(1) } as never,
    );
    await mount();
    expect(await screen.findByText("message 1")).toBeTruthy();
    expect(screen.getAllByText(/^message \d+$/)).toHaveLength(1);
    expect(screen.queryByText("No messages yet — say something below to start.")).toBeNull();
  });

  it("an EMPTY thread still shows its empty state", async () => {
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: META, messages: [] } as never,
    );
    await mount();
    expect(
      await screen.findByText("No messages yet — say something below to start."),
    ).toBeTruthy();
  });

  it("a new message appears at the TOP, next to the composer", async () => {
    vi.mocked(api.getThread).mockResolvedValue(
      { meta: { ...META, message_count: 2 }, messages: msgs(2) } as never,
    );
    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: { ...META, message_count: 4 },
      user_message: { role: "user", content: "message 3", ts_ms: 2000, model: null },
      assistant_message: { role: "assistant", content: "message 4", ts_ms: 2001, model: "m" },
    } as never);
    await mount();
    await screen.findByText("message 2");

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Compose message"), "hi");
    await user.click(screen.getByRole("button", { name: /^SEND$/ }));

    await waitFor(() => expect(screen.getByText("message 4")).toBeTruthy());
    const bodies = screen.getAllByText(/^message \d+$/).map((n) => n.textContent);
    expect(bodies[0]).toBe("message 4");
    expect(within(document.body).getByText("message 1")).toBeTruthy();
  });
});
