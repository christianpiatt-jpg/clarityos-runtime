/**
 * #180b (3) -- /me on the cockpit welcome card: the kernel block, the
 * capabilities the server lists, the vault flag as a word. Absent -> "—".
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

const profileState: { value: unknown } = { value: null };

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    getProfile: () => profileState.value,
    listOperatorSessions: vi.fn(async () => ({ sessions: [] })),
    getSessionDetail: vi.fn(),
    getOperatorVault: vi.fn(),
  };
});

import OperatorWelcome from "../OperatorWelcome";

const DASH = "—";

const FULL = {
  user: "u@example.com", operator_id: "op_x", tier: "free", cohort: "controller",
  member_number: 1, citizen: true, controller: true, citz_id: "citz-000001chr",
  billing_expires_at: null, vault_ready: true, eso_source: "none", external_signal_mode: "cloud_only",
  capabilities: [
    { id: "threads", label: "Threads", route: "/me/threads" },
    { id: "elins_v2", label: "ELINS v2 (Path C)", route: "/elins/v2/run" },
  ],
  intelligence_kernel: {
    version: "kernel.v1.0", external_signal_mode: "cloud_only", eso_source: "none", preferred_model: null,
    last_model_used: "anthropic:claude-haiku-4-5-20251001", local_model_usage_count: 0, vault_keys: 89,
    notes_count: 1, embeddings_count: 0, thread_count: 5, last_thread_updated_at: 1_788_546_510_783,
  },
};

beforeEach(() => { profileState.value = FULL; });

describe("OperatorWelcome (#180b 3)", () => {
  it("★ the kernel rows, each titled with its key", () => {
    render(<OperatorWelcome />);
    const env = screen.getByTestId("environment");
    expect(within(env).getByTestId("env-last_model_used")).toHaveTextContent("anthropic:claude-haiku-4-5-20251001");
    expect(within(env).getByTestId("env-version")).toHaveTextContent("kernel.v1.0");
    expect(within(env).getByTestId("env-thread_count")).toHaveTextContent("5");
    expect(within(env).getByTestId("env-notes_count")).toHaveTextContent("1");
    expect(within(env).getByTestId("env-embeddings_count")).toHaveTextContent("0");
    expect(within(env).getByTestId("env-vault_keys")).toHaveTextContent("89");
    expect(within(env).getByTestId("env-external_signal_mode")).toHaveTextContent("cloud_only");
    expect(within(env).getByTestId("env-eso_source")).toHaveTextContent("none");
    expect(within(env).getByTestId("env-preferred_model")).toHaveTextContent(DASH);
    expect(within(env).getByTestId("env-local_model_usage_count")).toHaveTextContent("0");
    expect(within(env).getByTestId("env-last_thread_updated_at")).toHaveTextContent("2026-09-04 18:28Z");
    expect(within(env).getByTitle("intelligence_kernel.last_model_used")).toBeInTheDocument();
    expect(within(env).getByTitle("intelligence_kernel.external_signal_mode · external_signal_mode")).toBeInTheDocument();
  });
  it("★ the capabilities the server lists, the route in the title", () => {
    render(<OperatorWelcome />);
    const caps = screen.getByTestId("capabilities");
    expect(within(caps).getByTestId("cap-threads")).toHaveTextContent("Threads");
    expect(within(caps).getByTestId("cap-threads")).toHaveAttribute("title", "capabilities[].id threads · capabilities[].route /me/threads");
    expect(within(caps).getByTestId("cap-elins_v2")).toHaveTextContent("/elins/v2/run");
  });
  it("vault_ready is a word; the identity rows carry their keys", () => {
    render(<OperatorWelcome />);
    expect(screen.getByTestId("vault-ready")).toHaveTextContent("ready");
    expect(screen.getByTitle("vault_ready")).toBeInTheDocument();
    expect(screen.getByTitle("tier")).toHaveTextContent("free");
    expect(screen.getByTitle("billing_expires_at")).toHaveTextContent(DASH);
  });
  it("absent: every kernel row a dash, no capabilities a dash, the flag a dash", () => {
    profileState.value = { user: "u@example.com" };
    render(<OperatorWelcome />);
    expect(screen.getByTestId("env-last_model_used")).toHaveTextContent(DASH);
    expect(screen.getByTestId("env-last_thread_updated_at")).toHaveTextContent(DASH);
    expect(screen.getByTestId("capabilities")).toHaveTextContent(DASH);
    expect(screen.getByTestId("vault-ready")).toHaveTextContent(DASH);
  });
  it("vault_ready false reads not ready", () => {
    profileState.value = { ...FULL, vault_ready: false };
    render(<OperatorWelcome />);
    expect(screen.getByTestId("vault-ready")).toHaveTextContent("not ready");
  });
});
