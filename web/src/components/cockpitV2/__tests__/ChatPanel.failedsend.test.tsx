/**
 * ★★ A FAILED SEND MUST NOT VANISH.
 *
 * ChatPanel clears the composer the instant send() is called, and a failed
 * send never reaches `messages`. So before this, a failure DELETED what the
 * member typed and left a bare error banner at the TOP of a pane full of
 * successfully-persisted history — no visual difference between "sent" and
 * "gone", and nothing to retry from.
 *
 * The passing case alone proves nothing, which is why the failing case is
 * tested first and asserted hardest.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    createThread: vi.fn(),
    getThread: vi.fn(),
    postThreadMessage: vi.fn(),
    summarizeThread: vi.fn(),
    renameThread: vi.fn(),
    deleteThread: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import ChatPanel from "../ChatPanel";
import { cockpit } from "../../../state/cockpitStore";

const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
};

beforeEach(() => {
  vi.mocked(api.listThreads).mockResolvedValue([META] as never);
  vi.mocked(api.getThread).mockResolvedValue({ meta: META, messages: [] } as never);
});
afterEach(() => vi.clearAllMocks());

async function mount() {
  render(<ChatPanel />);
  await act(async () => { await cockpit.thread.actions.init(); });
  await waitFor(() => expect(screen.getByPlaceholderText("Message…")).toBeEnabled());
}

async function send(text: string) {
  await userEvent.type(screen.getByPlaceholderText("Message…"), text);
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));
}

describe("ChatPanel — the failed send", () => {
  it("★ NEGATIVE CONTROL: a failed send keeps the text and shows the reason", async () => {
    vi.mocked(api.postThreadMessage).mockRejectedValue(
      new Error("missing_idempotency_key"),
    );
    await mount();
    await send("words I do not want to lose");

    const failed = await screen.findByTestId("failed-send");
    // The member's actual words survive — this is the whole point.
    expect(failed).toHaveTextContent("words I do not want to lose");
    // The reason is attached to the attempt, not floating at the top.
    expect(screen.getByTestId("failed-send-error"))
      .toHaveTextContent("missing_idempotency_key");
    // And it is visually distinct from persisted history.
    expect(failed.className).toContain("cv2-msg-failed");
  });

  it("offers a retry that re-sends the same text", async () => {
    vi.mocked(api.postThreadMessage).mockRejectedValueOnce(new Error("boom"));
    await mount();
    await send("retry me");
    await screen.findByTestId("failed-send");

    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: { ...META, message_count: 2 },
      user_message: { role: "user", content: "retry me", ts_ms: 10, model: null },
      assistant_message: { role: "assistant", content: "ok", ts_ms: 11, model: "m" },
    } as never);
    await userEvent.click(screen.getByTestId("failed-send-retry"));

    await waitFor(() => expect(screen.queryByTestId("failed-send")).toBeNull());
    expect(await screen.findByText("ok")).toBeTruthy();
    expect(vi.mocked(api.postThreadMessage).mock.calls.at(-1)?.[1]).toBe("retry me");
  });

  it("offers an edit that returns the text to the composer", async () => {
    vi.mocked(api.postThreadMessage).mockRejectedValue(new Error("boom"));
    await mount();
    await send("let me fix this");
    await screen.findByTestId("failed-send");

    await userEvent.click(screen.getByTestId("failed-send-edit"));
    expect(screen.getByPlaceholderText("Message…")).toHaveValue("let me fix this");
    expect(screen.queryByTestId("failed-send")).toBeNull();
  });

  it("PASSING CASE: a successful send shows no failure state", async () => {
    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: { ...META, message_count: 2 },
      user_message: { role: "user", content: "hello", ts_ms: 10, model: null },
      assistant_message: { role: "assistant", content: "hi", ts_ms: 11, model: "m" },
    } as never);
    await mount();
    await send("hello");

    expect(await screen.findByText("hi")).toBeTruthy();
    expect(screen.queryByTestId("failed-send")).toBeNull();
  });

  it("a second send clears the previous failure", async () => {
    vi.mocked(api.postThreadMessage).mockRejectedValueOnce(new Error("boom"));
    await mount();
    await send("first");
    await screen.findByTestId("failed-send");

    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: { ...META, message_count: 2 },
      user_message: { role: "user", content: "second", ts_ms: 12, model: null },
      assistant_message: { role: "assistant", content: "ok", ts_ms: 13, model: "m" },
    } as never);
    await send("second");
    await waitFor(() => expect(screen.queryByTestId("failed-send")).toBeNull());
  });
});
