/**
 * #118 — the Sessions empty state stops promising a chat surface that landed.
 *
 * ★ WHAT THIS PINS. The copy said "web threads will appear here once a chat
 * surface lands on web". It landed: /cockpit. The empty state now says
 * where web threads live and links there, and never says the old sentence.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Sessions from "../Sessions";

describe("Sessions — empty-state copy (#118)", () => {
  beforeEach(() => {
    try { localStorage.clear(); } catch { /* noop */ }
  });

  it("says web threads live in the Cockpit and links to /cockpit", () => {
    render(<MemoryRouter><Sessions /></MemoryRouter>);
    const empty = screen.getByTestId("sessions-empty");
    expect(empty).toHaveTextContent("Web threads live in the Cockpit (/cockpit).");
    expect(empty).toHaveTextContent("This page lists threads stored on this device.");
    const link = empty.querySelector('a[href="/cockpit"]');
    expect(link).not.toBeNull();
  });

  it("never says the old sentence", () => {
    render(<MemoryRouter><Sessions /></MemoryRouter>);
    expect(screen.getByTestId("sessions-empty").textContent).not.toMatch(/chat surface lands/);
    expect(screen.getByTestId("sessions-empty").textContent).not.toMatch(/will appear here/);
  });
});
