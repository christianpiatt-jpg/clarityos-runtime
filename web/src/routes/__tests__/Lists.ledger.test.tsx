/**
 * #180b (5) -- the timeline and vault lists render what the wire carries:
 * the tag is the event's SOURCE (the raw kind tag is gone, K3 C-iv), the
 * wire's count, and size / stamps in titles.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, timelineList: vi.fn(), vaultList: vi.fn() };
});

import * as api from "../../lib/api";
import Timeline from "../Timeline";
import Vault from "../Vault";

const DASH = "—";

const EVENTS = [
  { id: "t1", user: "u", kind: "library.ingest", summary: "ingested", ref: "l_1", ts: 1_788_553_496,
    data: { tags: ["x"], ingestion_version: "ingestion.v1.0", source: "elins_v2_view" }, created_at: 1_788_553_496, size_bytes: 0 },
  { id: "t2", user: "u", kind: "vault.write", summary: "wrote", ref: null, ts: 1_788_553_400, data: {}, created_at: 1_788_553_400, size_bytes: 512 },
];

const ITEMS = [
  { id: "v1", user: "u", type: "note", title: "Doctrine", content: "c", tags: ["doctrine"], created_at: 1_788_449_242, updated_at: 1_788_449_259, size_bytes: 56_544 },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.timelineList).mockResolvedValue({ ok: true, events: EVENTS, count: 4 } as never);
  vi.mocked(api.vaultList).mockResolvedValue({ ok: true, items: ITEMS, count: 2 } as never);
});

describe("Timeline (#180b 5)", () => {
  it("★ the tag is the source; an event without one reads a dash; the raw kind tag is gone", async () => {
    render(<MemoryRouter><Timeline /></MemoryRouter>);
    const tags = await screen.findAllByTestId("tl-tag");
    expect(tags[0]).toHaveTextContent("elins_v2_view");
    expect(tags[1]).toHaveTextContent(DASH);
    expect(screen.queryByText("library.ingest", { selector: ".tag" })).toBeNull();
    expect(tags[0]).toHaveAttribute("title", "events[].data.source · events[].data.ingestion_version ingestion.v1.0 · events[].kind library.ingest · events[].created_at 2026-09-04 20:24Z · events[].size_bytes 0");
    expect(tags[1]).toHaveAttribute("title", `events[].data.source · events[].data.ingestion_version ${DASH} · events[].kind vault.write · events[].created_at 2026-09-04 20:23Z · events[].size_bytes 512`);
  });
  it("the wire's count, not the page length", async () => {
    render(<MemoryRouter><Timeline /></MemoryRouter>);
    await screen.findAllByTestId("tl-tag");
    expect(screen.getByTestId("tl-count")).toHaveTextContent("4 events");
  });
  it("no count on the wire reads a dash", async () => {
    vi.mocked(api.timelineList).mockResolvedValue({ ok: true, events: EVENTS } as never);
    render(<MemoryRouter><Timeline /></MemoryRouter>);
    await screen.findAllByTestId("tl-tag");
    expect(screen.getByTestId("tl-count")).toHaveTextContent(`${DASH} events`);
  });
});

describe("Vault (#180b 5)", () => {
  it("★ the wire's count; the row carries size and last update in its title; the pill its key", async () => {
    render(<MemoryRouter><Vault /></MemoryRouter>);
    const row = await screen.findByTestId("vault-row");
    expect(row).toHaveAttribute("title", "items[].size_bytes 56544 · items[].updated_at 2026-09-03 15:27Z");
    expect(screen.getByTestId("vault-count")).toHaveTextContent("2 items");
    expect(screen.getByTitle("items[].type")).toHaveTextContent("note");
  });
  it("absent size and stamp read dashes", async () => {
    vi.mocked(api.vaultList).mockResolvedValue({ ok: true, items: [{ ...ITEMS[0], size_bytes: undefined, updated_at: undefined }], count: 1 } as never);
    render(<MemoryRouter><Vault /></MemoryRouter>);
    const row = await screen.findByTestId("vault-row");
    expect(row).toHaveAttribute("title", `items[].size_bytes ${DASH} · items[].updated_at ${DASH}`);
    expect(screen.getByTestId("vault-count")).toHaveTextContent("1 item");
  });
});
