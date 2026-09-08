/**
 * #180b (3) -- /me's kernel block, capabilities and vault flag on the
 * member's own page. Present -> rendered; absent -> "—"; false -> its word.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const authState: { session: string | null; user: string | null; profile: unknown } = { session: "s", user: "u", profile: null };

vi.mock("../../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/auth")>("../../../lib/auth");
  return { ...actual, getAuthSnapshot: () => authState, subscribeAuth: () => () => {} };
});

import KernelFacts from "../KernelFacts";

const DASH = "—";
const FULL = {
  user: "u", tier: "free", billing_expires_at: 1_789_924_478, vault_ready: true,
  eso_source: "none", external_signal_mode: "cloud_only",
  capabilities: [{ id: "threads", label: "Threads", route: "/me/threads" }, { id: "elins_v2", label: "ELINS v2 (Path C)", route: "/elins/v2/run" }],
  intelligence_kernel: {
    version: "kernel.v1.0", external_signal_mode: "cloud_only", eso_source: "none", preferred_model: null,
    last_model_used: "anthropic:claude-haiku-4-5-20251001", local_model_usage_count: 0, vault_keys: 89,
    notes_count: 1, embeddings_count: 0, thread_count: 5, last_thread_updated_at: 1_788_546_510_783,
  },
};

beforeEach(() => { authState.profile = FULL; });

describe("KernelFacts (#180b 3, the member surface)", () => {
  it("★ the kernel rows, the flag as a word, the capabilities on one line, every key titled", () => {
    render(<KernelFacts />);
    expect(screen.getByTestId("kf-last_model_used")).toHaveTextContent("anthropic:claude-haiku-4-5-20251001");
    expect(screen.getByTestId("kf-version")).toHaveTextContent("kernel.v1.0");
    expect(screen.getByTestId("kf-thread_count")).toHaveTextContent("5");
    expect(screen.getByTestId("kf-vault_keys")).toHaveTextContent("89");
    expect(screen.getByTestId("kf-preferred_model")).toHaveTextContent(DASH);
    expect(screen.getByTestId("kf-last_thread_updated_at")).toHaveTextContent("2026-09-04 18:28Z");
    expect(screen.getByTestId("kf-vault_ready")).toHaveTextContent("ready");
    expect(screen.getByTestId("kf-tier")).toHaveTextContent("free");
    expect(screen.getByTestId("kf-billing_expires_at")).toHaveTextContent("2026-09-20");
    expect(screen.getByTestId("kf-capabilities")).toHaveTextContent("Threads · ELINS v2 (Path C)");
    expect(screen.getByTitle("capabilities[].id threads · capabilities[].label · capabilities[].route /me/threads")).toBeInTheDocument();
    expect(screen.getByTitle("intelligence_kernel.external_signal_mode · external_signal_mode")).toBeInTheDocument();
  });
  it("absent: dashes everywhere; false reads not ready", () => {
    authState.profile = { user: "u", vault_ready: false };
    render(<KernelFacts />);
    expect(screen.getByTestId("kf-last_model_used")).toHaveTextContent(DASH);
    expect(screen.getByTestId("kf-capabilities")).toHaveTextContent(DASH);
    expect(screen.getByTestId("kf-vault_ready")).toHaveTextContent("not ready");
    expect(screen.getByTestId("kf-billing_expires_at")).toHaveTextContent(DASH);
  });
  it("no profile at all: still renders, dashed", () => {
    authState.profile = null;
    render(<KernelFacts />);
    expect(screen.getByTestId("kf-vault_ready")).toHaveTextContent(DASH);
  });
});
