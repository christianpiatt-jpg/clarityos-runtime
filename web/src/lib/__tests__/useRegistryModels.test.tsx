/**
 * useRegistryModels — the ids a picker may offer come from the server.
 *
 * ★ WHAT THESE PIN. registry -> ids = supported with "auto" first and no
 * duplicates; fetch failure -> the fallback constant, labelled; an EMPTY
 * registry is not a registry -> fallback, labelled with its own reason.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  getProviderModels: vi.fn(),
}));

import { getProviderModels, V44_MODEL_IDS } from "../api";
import { useRegistryModels } from "../useRegistryModels";

const models = vi.mocked(getProviderModels);

describe("useRegistryModels", () => {
  beforeEach(() => { models.mockReset(); });

  it("registry: supported ids, auto first, de-duplicated", async () => {
    models.mockResolvedValue({
      registry: {},
      supported: ["openai:gpt-5.4", "auto", "anthropic:claude-haiku-4-5-20251001", "openai:gpt-5.4"],
    });
    const { result } = renderHook(() => useRegistryModels());
    expect(result.current.source).toBe("loading");
    await waitFor(() => expect(result.current.source).toBe("registry"));
    expect(result.current.ids).toEqual(["auto", "openai:gpt-5.4", "anthropic:claude-haiku-4-5-20251001"]);
    expect(result.current.error).toBeNull();
  });

  it("fetch failure: the fallback constant, source 'fallback', error kept", async () => {
    models.mockRejectedValue(new Error("HTTP 503"));
    const { result } = renderHook(() => useRegistryModels());
    await waitFor(() => expect(result.current.source).toBe("fallback"));
    expect(result.current.ids).toEqual(V44_MODEL_IDS);
    expect(result.current.error).toBe("HTTP 503");
  });

  it("★ an empty registry is not a registry: fallback, with its own reason", async () => {
    models.mockResolvedValue({ registry: {}, supported: [] });
    const { result } = renderHook(() => useRegistryModels());
    await waitFor(() => expect(result.current.source).toBe("fallback"));
    expect(result.current.ids).toEqual(V44_MODEL_IDS);
    expect(result.current.error).toMatch(/no models/);
  });

  it("the fallback itself carries only ids the router accepts (mirrors MODEL_REGISTRY)", () => {
    // pinned by value so a registry change is a visible test change, not drift
    expect(V44_MODEL_IDS).toEqual([
      "auto",
      "openai:gpt-5.4",
      "openai:gpt-5.4-mini",
      "anthropic:claude-haiku-4-5-20251001",
      "google:gemini-2.5-flash",
      "xai:groq-llama",
      "local:llama3.1",
      "ollama:llama3.1",
      "deepseek:deepseek-v4-flash",
      "deepseek:deepseek-v4-pro",
      "mistral:mistral-large-2512",
    ]);
    expect(V44_MODEL_IDS.join(" ")).not.toMatch(/gpt-4\.2|claude-3\.7|gemini-2\.0/);
  });
});
