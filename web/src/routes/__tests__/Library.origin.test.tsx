/**
 * #138 -- a library item says where it came from, on the /library detail.
 *
 * ★ WHAT THESE PIN. The five provenance keys render under the tags from
 * metadata TOP LEVEL, each with its wire path in a title; a null (every
 * item written before the stamp) reads a dash -- not a zero, not "none".
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  libraryUserList: vi.fn(),
  libraryUserWrite: vi.fn(),
  libraryUserUpdate: vi.fn(),
}));

import { libraryUserList } from "../../lib/api";
import Library from "../Library";

const WITH = {
  id: "l1", user: "u", title: "kept from the tab", content: "the text", tags: ["elins_v2_ingestion", "elins_v2_view"],
  metadata: {
    source: "elins_v2_view", origin_route: "thread_footer", origin_thread_id: "t9",
    origin_turn_id: null, run_id: null, created_ts: 1_788_890_000.5,
  },
  created_at: 1_788_890_000, updated_at: 1_788_890_000, size_bytes: 8,
};
const LEGACY = {
  id: "l0", user: "u", title: "an item from 09-03", content: "older", tags: ["elins_v2_ingestion"],
  metadata: { source: "manual", ingestion_version: "ingestion.v1.0" },
  created_at: 1_788_800_000, updated_at: 1_788_800_000, size_bytes: 5,
};

const DASH = "—";

async function mountAndOpen(title: string) {
  vi.mocked(libraryUserList).mockResolvedValue({ ok: true, items: [WITH, LEGACY], count: 2 } as never);
  render(<MemoryRouter><Library /></MemoryRouter>);
  const row = await screen.findByText(title);
  fireEvent.click(row);
  await waitFor(() => expect(screen.getByTestId("lib-origin-route")).toBeInTheDocument());
}

beforeEach(() => vi.clearAllMocks());

describe("Library detail — provenance (#138)", () => {
  it("★ an item with its origin renders the route and the thread; the absent ones read a dash", async () => {
    await mountAndOpen("kept from the tab");
    expect(screen.getByTestId("lib-origin-route")).toHaveTextContent("thread_footer");
    expect(screen.getByTestId("lib-origin-thread")).toHaveTextContent("t9");
    expect(screen.getByTestId("lib-origin-turn")).toHaveTextContent(DASH);
    expect(screen.getByTestId("lib-run-id")).toHaveTextContent(DASH);
    expect(screen.getByTestId("lib-created-ts")).not.toHaveTextContent(DASH);
    expect(screen.getByTitle("metadata.origin_route")).toBeInTheDocument();
    expect(screen.getByTitle("metadata.created_ts")).toBeInTheDocument();
  });

  it("an item written before the stamp reads dashes everywhere -- not zeros, not 'none'", async () => {
    await mountAndOpen("an item from 09-03");
    for (const id of ["lib-origin-route", "lib-origin-thread", "lib-origin-turn", "lib-run-id", "lib-created-ts"]) {
      expect(screen.getByTestId(id)).toHaveTextContent(DASH);
    }
    expect(screen.getByTestId("lib-origin-route")).not.toHaveTextContent(/none|0/);
  });
});
