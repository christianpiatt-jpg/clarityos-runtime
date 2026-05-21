// Iframe route smoke tests. localStorage and URL search params are
// the only side effects; no API calls so nothing needs mocking.

import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import Iframe from "../Iframe";

function renderWithRouter(initialEntry = "/iframe") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Iframe />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("Iframe route", () => {
  test("renders empty state when no URL is loaded", () => {
    renderWithRouter();
    expect(screen.getByRole("heading", { name: /IFRAME/i })).toBeInTheDocument();
    expect(screen.getByText(/No URL loaded/i)).toBeInTheDocument();
    expect(screen.queryByTitle("ClarityOS iframe surface")).not.toBeInTheDocument();
  });

  test("loads URL passed via ?src= and renders the iframe", () => {
    renderWithRouter("/iframe?src=https://example.com");
    const frame = screen.getByTitle("ClarityOS iframe surface") as HTMLIFrameElement;
    expect(frame).toBeInTheDocument();
    expect(frame.src).toBe("https://example.com/");
    expect(screen.getByText(/src: https:\/\/example\.com/)).toBeInTheDocument();
  });

  test("LOAD button is disabled until a normalizable URL is typed", async () => {
    const user = userEvent.setup();
    renderWithRouter();
    const loadBtn = screen.getByRole("button", { name: "LOAD" });
    expect(loadBtn).toBeDisabled();

    const input = screen.getByLabelText("URL") as HTMLInputElement;
    await user.type(input, "https://pro-mediations.com/wp-admin/");
    expect(loadBtn).not.toBeDisabled();

    await user.click(loadBtn);
    const frame = await screen.findByTitle("ClarityOS iframe surface") as HTMLIFrameElement;
    expect(frame.src).toBe("https://pro-mediations.com/wp-admin/");
  });

  test("rejects javascript: and other non-http(s) URLs", async () => {
    const user = userEvent.setup();
    renderWithRouter();
    const input = screen.getByLabelText("URL") as HTMLInputElement;
    await user.type(input, "javascript:alert(1)");
    expect(screen.getByRole("button", { name: "LOAD" })).toBeDisabled();
  });

  test("SAVE BOOKMARK persists to localStorage and renders a chip", async () => {
    const user = userEvent.setup();
    renderWithRouter();
    const input = screen.getByLabelText("URL") as HTMLInputElement;
    await user.type(input, "https://pro-mediations.com/wp-admin/");
    await user.click(screen.getByRole("button", { name: "SAVE BOOKMARK" }));

    // chip rendered (uses hostname as default label)
    expect(screen.getByRole("button", { name: "pro-mediations.com" })).toBeInTheDocument();

    // and persisted
    const raw = localStorage.getItem("clarityos_iframe_bookmarks");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].url).toBe("https://pro-mediations.com/wp-admin/");
  });

  test("resumes ?src from the URL on remount", () => {
    renderWithRouter("/iframe?src=https://example.org/admin");
    const frame = screen.getByTitle("ClarityOS iframe surface") as HTMLIFrameElement;
    expect(frame.src).toBe("https://example.org/admin");
  });
});
