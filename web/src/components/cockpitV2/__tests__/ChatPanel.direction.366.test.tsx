/**
 * #366 -- the direction bit on the cockpit composer (R-366-B), the relation
 * label the reading names (A8), and the sovereign seat named on the page
 * (A6).
 *
 * Every test names the mutation that breaks it.
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
    markovEnvelopeLatest: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import ChatPanel from "../ChatPanel";
import { cockpit } from "../../../state/cockpitStore";

const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
};

function reply(over: Partial<api.ThreadMessageResult> = {}): api.ThreadMessageResult {
  return {
    meta: { ...META, message_count: 2 },
    user_message: { role: "user", content: "hello", ts_ms: 10, model: null },
    assistant_message: { role: "assistant", content: "reading · relation: complainant ↔ agency · rows 3", ts_ms: 11, model: "openai:gpt-5.4" },
    model_id: "openai:gpt-5.4",
    direction: "query",
    picked: false,
    reading: { relation: "complainant ↔ agency", rows: 3, robust: 2, contested: 1, undefined: 0, lanes: ["time", "ambient", "role"] },
    sovereign: null,
    ...over,
  };
}

beforeEach(() => {
  vi.mocked(api.listThreads).mockResolvedValue([META] as never);
  vi.mocked(api.getThread).mockResolvedValue({ meta: META, messages: [] } as never);
  vi.mocked(api.markovEnvelopeLatest).mockRejectedValue(new Error("no_state"));
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

describe("ChatPanel — the direction bit (R-366-B)", () => {
  it("is pre-set to query and an untouched send carries query/unpicked", async () => {
    // Mutation: send the body without the bit -> the third argument is undefined.
    vi.mocked(api.postThreadMessage).mockResolvedValue(reply());
    await mount();
    const select = screen.getByTestId("thread-direction") as HTMLSelectElement;
    expect(select.value).toBe("query");
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["query", "action", "plan", "diagnostic"]);
    await send("hello");
    expect(api.postThreadMessage).toHaveBeenCalledWith("t1", "hello", { direction: "query", picked: false });
  });

  it("a picked word rides the send with picked=true and stays for the next turn", async () => {
    // Mutation: reset the selector after a send -> the second send carries query.
    vi.mocked(api.postThreadMessage).mockResolvedValue(reply({ direction: "plan", picked: true }));
    await mount();
    await userEvent.selectOptions(screen.getByTestId("thread-direction"), "plan");
    await send("plan the week");
    expect(api.postThreadMessage).toHaveBeenLastCalledWith("t1", "plan the week", { direction: "plan", picked: true });
    await send("and the month");
    expect(api.postThreadMessage).toHaveBeenLastCalledWith("t1", "and the month", { direction: "plan", picked: true });
  });

  it("picking query explicitly is still a pick", async () => {
    // Mutation: picked = direction !== "query" -> false here.
    vi.mocked(api.postThreadMessage).mockResolvedValue(reply({ picked: true }));
    await mount();
    await userEvent.selectOptions(screen.getByTestId("thread-direction"), "action");
    await userEvent.selectOptions(screen.getByTestId("thread-direction"), "query");
    await send("hello");
    expect(api.postThreadMessage).toHaveBeenLastCalledWith("t1", "hello", { direction: "query", picked: true });
  });
});

describe("ChatPanel — the relation label (A8) and the sovereign seat (A6)", () => {
  it("renders the relation the reading names, and nothing when it named none", async () => {
    // Mutation: render the label for "undefined" -> a label with the word undefined.
    vi.mocked(api.postThreadMessage)
      .mockResolvedValueOnce(reply())
      .mockResolvedValueOnce(reply({ reading: { relation: "undefined", rows: 0 } }));
    await mount();
    await send("hello");
    expect(await screen.findByTestId("reading-relation")).toHaveTextContent("relation: complainant ↔ agency");
    await send("again");
    await waitFor(() => expect(screen.getAllByText(/^assistant$/).length).toBe(2));
    expect(screen.getAllByTestId("reading-relation")).toHaveLength(1);
  });

  it("names the sovereign seat when a diagnostic turn came back un-provisioned", async () => {
    // Mutation: render on mock alone / never render -> the line is missing.
    vi.mocked(api.postThreadMessage).mockResolvedValue(reply({
      direction: "diagnostic", picked: true, sovereign: "not_provisioned",
      assistant_message: { role: "assistant", content: "sovereign seat not provisioned — no local model answered; 2 rows carried no reading", ts_ms: 11, model: "local:llama3.1" },
      reading: { relation: "undefined", rows: 2, provisioned: false },
    }));
    await mount();
    await userEvent.selectOptions(screen.getByTestId("thread-direction"), "diagnostic");
    await send("what is my state");
    expect(await screen.findByTestId("sovereign-not-provisioned")).toHaveTextContent("sovereign seat not provisioned");
    expect(screen.queryByTestId("reading-relation")).toBeNull();
  });

  it("a provisioned or non-diagnostic turn shows no sovereign line", async () => {
    vi.mocked(api.postThreadMessage).mockResolvedValue(reply({ sovereign: null }));
    await mount();
    await send("hello");
    await screen.findByTestId("reading-relation");
    expect(screen.queryByTestId("sovereign-not-provisioned")).toBeNull();
  });
});
