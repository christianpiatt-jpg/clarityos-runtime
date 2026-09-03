/**
 * #126 — the founder override picker offers only ids the router accepts.
 *
 * ★ WHAT THIS PINS. The options come from GET /runtime/providers/models
 * (the registry), never from a client constant; every option is in the
 * server's `supported` list; choosing one sends that exact id. When the
 * registry fetch fails the picker falls back to the built-in list AND says
 * "registry unavailable" -- it never silently pretends.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("../../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  founderModelsStatus: vi.fn(),
  founderModelsOverride: vi.fn(),
  getProviderModels: vi.fn(),
}));

import {
  founderModelsStatus, founderModelsOverride, getProviderModels, V44_MODEL_IDS,
} from "../../../../lib/api";
import FounderModelStatusPanel from "../FounderModelStatusPanel";

const status = vi.mocked(founderModelsStatus);
const override = vi.mocked(founderModelsOverride);
const models = vi.mocked(getProviderModels);

const SUPPORTED = [
  "openai:gpt-5.4", "openai:gpt-5.4-mini",
  "anthropic:claude-haiku-4-5-20251001",
  "google:gemini-2.5-flash",
  "auto",
];

function router() {
  return {
    ok: true as const,
    // present on the override response type; harmless on the status one
    default_model: null as string | null,
    router: {
      version: "v44",
      supported_models: SUPPORTED,
      task_defaults: {},
      founder_default_model: null,
      providers: { anthropic: { configured: true } },
    },
  };
}

function options(): string[] {
  const sel = screen.getByTestId("model-picker") as HTMLSelectElement;
  return Array.from(sel.options).map((o) => o.value).filter((v) => v !== "");
}

describe("FounderModelStatusPanel — registry-driven picker (#126)", () => {
  beforeEach(() => {
    status.mockReset(); override.mockReset(); models.mockReset();
    status.mockResolvedValue(router());
  });

  it("★ options are exactly the registry's supported ids, auto first", async () => {
    models.mockResolvedValue({
      registry: { openai: SUPPORTED.slice(0, 2), anthropic: [SUPPORTED[2]], google: [SUPPORTED[3]] },
      supported: SUPPORTED,
    });
    render(<FounderModelStatusPanel />);
    await waitFor(() => expect(options().length).toBeGreaterThan(0));
    const opts = options();
    expect(opts[0]).toBe("auto");
    for (const o of opts) expect(SUPPORTED).toContain(o);
    expect(new Set(opts)).toEqual(new Set(SUPPORTED));
    // none of the old lies
    expect(opts.join(" ")).not.toMatch(/gpt-4\.2|claude-3\.7|gemini-2\.0/);
    expect(screen.queryByTestId("registry-fallback")).toBeNull();
  });

  it("selecting an option sends that exact registry id", async () => {
    models.mockResolvedValue({ registry: {}, supported: SUPPORTED });
    override.mockResolvedValue(router());
    render(<FounderModelStatusPanel />);
    await waitFor(() => expect(options().length).toBeGreaterThan(0));
    fireEvent.change(screen.getByTestId("model-picker"), { target: { value: "anthropic:claude-haiku-4-5-20251001" } });
    await waitFor(() => expect(override).toHaveBeenCalledTimes(1));
    expect(override).toHaveBeenCalledWith("anthropic:claude-haiku-4-5-20251001");
  });

  it("★ registry fetch fails -> built-in list, labelled 'registry unavailable'", async () => {
    models.mockRejectedValue(new Error("HTTP 503"));
    render(<FounderModelStatusPanel />);
    await waitFor(() => expect(screen.getByTestId("registry-fallback")).toBeInTheDocument());
    expect(screen.getByTestId("registry-fallback")).toHaveTextContent("registry unavailable");
    expect(options()).toEqual(V44_MODEL_IDS);
  });
});
