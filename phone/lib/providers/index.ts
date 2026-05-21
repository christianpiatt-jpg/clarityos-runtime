import type { AIProvider, ProviderId } from "./types";
import { ClaudeProvider } from "./ClaudeProvider";
import { ChatGPTProvider } from "./ChatGPTProvider";
import { GeminiProvider } from "./GeminiProvider";
import { CopilotProvider } from "./CopilotProvider";
import { LocalProvider } from "./LocalProvider";

const PROVIDERS: AIProvider[] = [
  ClaudeProvider,
  ChatGPTProvider,
  GeminiProvider,
  CopilotProvider,
  LocalProvider,
];

export function getProviders(): AIProvider[] {
  return PROVIDERS;
}

export function getProviderById(id: ProviderId): AIProvider | undefined {
  return PROVIDERS.find((p) => p.id === id);
}

export type { AIProvider, ProviderId, ProviderResult } from "./types";
