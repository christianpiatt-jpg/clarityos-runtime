/**
 * AddToCorpusBox — the corpus front door in the cockpit.
 *
 * ★ WHAT THESE PIN. The box exists; its button is disabled on empty (and
 * whitespace-only) text and while a post is in flight; pressing it posts the
 * trimmed text through ingestManual with source "cockpit" exactly once;
 * success shows the item id and a router Link to /library and clears the
 * box; failure is shown as an error (class cv2-err, not a muted note) and
 * the text is kept -- nothing was stored.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  ingestManual: vi.fn(),
}));

import { ingestManual } from "../../../lib/api";
import AddToCorpusBox from "../AddToCorpusBox";

const mocked = vi.mocked(ingestManual);
const OK = { ok: true as const, library_id: "l_new1", envelope: {} };

function mount() {
  return render(<MemoryRouter><AddToCorpusBox /></MemoryRouter>);
}

describe("AddToCorpusBox", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("renders the box with its button disabled on empty text", () => {
    mount();
    expect(screen.getByTestId("add-to-corpus")).toBeInTheDocument();
    expect(screen.getByTestId("corpus-submit")).toBeDisabled();
  });

  it("whitespace-only text keeps the button disabled", () => {
    mount();
    fireEvent.change(screen.getByTestId("corpus-text"), { target: { value: "   \n " } });
    expect(screen.getByTestId("corpus-submit")).toBeDisabled();
  });

  it("★ text in -> one press -> ingestManual called with the text, id + /library link shown", async () => {
    mocked.mockResolvedValue(OK);
    mount();
    fireEvent.change(screen.getByTestId("corpus-text"), { target: { value: "  three sentences. here. now.  " } });
    const btn = screen.getByTestId("corpus-submit");
    expect(btn).toBeEnabled();
    fireEvent.click(btn);

    await waitFor(() => expect(screen.getByTestId("corpus-result")).toBeInTheDocument());
    expect(mocked).toHaveBeenCalledTimes(1);
    expect(mocked).toHaveBeenCalledWith({ text: "three sentences. here. now.", source: "cockpit" });
    const result = screen.getByTestId("corpus-result");
    expect(result).toHaveTextContent("l_new1");
    // a router Link renders as <a href="/library"> under MemoryRouter
    expect(result.querySelector('a[href="/library"]')).not.toBeNull();
    // the textarea is cleared for the next paste; button back to disabled
    expect(screen.getByTestId("corpus-text")).toHaveValue("");
    expect(screen.getByTestId("corpus-submit")).toBeDisabled();
  });

  it("while the post is in flight the button and textarea are disabled and say so", async () => {
    let settle!: (v: typeof OK) => void;
    mocked.mockImplementation(() => new Promise<typeof OK>((r) => { settle = r; }));
    mount();
    fireEvent.change(screen.getByTestId("corpus-text"), { target: { value: "in flight" } });
    fireEvent.click(screen.getByTestId("corpus-submit"));

    await waitFor(() => expect(screen.getByTestId("corpus-submit")).toHaveTextContent("adding…"));
    expect(screen.getByTestId("corpus-submit")).toBeDisabled();
    expect(screen.getByTestId("corpus-text")).toBeDisabled();
    // a second press during flight does nothing
    fireEvent.click(screen.getByTestId("corpus-submit"));
    expect(mocked).toHaveBeenCalledTimes(1);

    settle(OK);
    await waitFor(() => expect(screen.getByTestId("corpus-result")).toBeInTheDocument());
    expect(screen.getByTestId("corpus-text")).toBeEnabled();
  });

  it("a failed post is shown as an error, not swallowed, and the text is kept", async () => {
    // a failure this endpoint can actually produce (request() network path)
    mocked.mockRejectedValue(new Error("Network unreachable"));
    mount();
    fireEvent.change(screen.getByTestId("corpus-text"), { target: { value: "kept?" } });
    fireEvent.click(screen.getByTestId("corpus-submit"));
    await waitFor(() => expect(screen.getByTestId("corpus-error")).toBeInTheDocument());
    const err = screen.getByTestId("corpus-error");
    expect(err).toHaveTextContent("Network unreachable");
    // reads as an error: the class applies, and no inline colour overrides it
    expect(err).toHaveClass("cv2-err");
    expect(err.style.color).toBe("");
    expect(screen.queryByTestId("corpus-result")).toBeNull();
    // the text is NOT cleared on failure -- nothing was kept
    expect(screen.getByTestId("corpus-text")).toHaveValue("kept?");
  });
});
