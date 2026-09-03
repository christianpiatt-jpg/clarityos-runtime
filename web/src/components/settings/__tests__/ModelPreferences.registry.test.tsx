/**
 * #126 — the /account model preference picker offers only registry ids.
 *
 * ★ WHAT THIS PINS. Same contract as the founder picker: options ⊆ the
 * server's `supported` list from GET /runtime/providers/models; choosing
 * one sends that exact id to /me/operator_state/model; a failed registry
 * fetch is labelled, never hidden.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  me: vi.fn(),
  meOperatorStateModel: vi.fn(),
  getProviderModels: vi.fn(),
}));

import { me, meOperatorStateModel, getProviderModels, V44_MODEL_IDS } from "../../../lib/api";
import ModelPreferences from "../ModelPreferences";

const meMock = vi.mocked(me);
const setModel = vi.mocked(meOperatorStateModel);
const models = vi.mocked(getProviderModels);

const SUPPORTED = ["openai:gpt-5.4", "anthropic:claude-haiku-4-5-20251001", "google:gemini-2.5-flash", "auto"];

function options(): string[] {
  const sel = screen.getByTestId("model-picker") as HTMLSelectElement;
  return Array.from(sel.options).map((o) => o.value).filter((v) => v !== "");
}

describe("ModelPreferences (account) — registry-driven picker (#126)", () => {
  beforeEach(() => {
    meMock.mockReset(); setModel.mockReset(); models.mockReset();
    meMock.mockResolvedValue({
      intelligence_kernel: { preferred_model: null, last_model_used: null, models: null },
    } as never);
  });

  it("★ options ⊆ registry supported ids; none of the old ids", async () => {
    models.mockResolvedValue({ registry: {}, supported: SUPPORTED });
    render(<ModelPreferences />);
    await waitFor(() => expect(options().length).toBeGreaterThan(0));
    const opts = options();
    for (const o of opts) expect(SUPPORTED).toContain(o);
    expect(opts[0]).toBe("auto");
    expect(opts.join(" ")).not.toMatch(/gpt-4\.2|claude-3\.7|gemini-2\.0/);
    expect(screen.queryByTestId("registry-fallback")).toBeNull();
  });

  it("selecting sends that exact id", async () => {
    models.mockResolvedValue({ registry: {}, supported: SUPPORTED });
    setModel.mockResolvedValue({ ok: true, state: {} } as never);
    render(<ModelPreferences />);
    await waitFor(() => expect(options().length).toBeGreaterThan(0));
    fireEvent.change(screen.getByTestId("model-picker"), { target: { value: "google:gemini-2.5-flash" } });
    await waitFor(() => expect(setModel).toHaveBeenCalledTimes(1));
    expect(setModel).toHaveBeenCalledWith("google:gemini-2.5-flash");
  });

  it("★ registry fetch fails -> built-in list, labelled", async () => {
    models.mockRejectedValue(new Error("network"));
    render(<ModelPreferences />);
    await waitFor(() => expect(screen.getByTestId("registry-fallback")).toBeInTheDocument());
    expect(options()).toEqual(V44_MODEL_IDS);
  });
});
