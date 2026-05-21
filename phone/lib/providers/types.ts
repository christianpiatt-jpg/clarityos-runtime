export type ProviderId = "claude" | "chatgpt" | "gemini" | "copilot" | "local";

export interface ProviderResult {
  // For now we only care about whether we successfully handed off the text.
  success: boolean;
  message?: string;
}

export interface AIProvider {
  id: ProviderId;
  name: string;
  sendMessage: (text: string) => Promise<ProviderResult>;
}
