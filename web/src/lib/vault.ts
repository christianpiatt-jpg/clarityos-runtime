// vault.ts — DEPRECATED. The localStorage-backed vault has been removed.
// All vault state now lives on the server via /vault/list, /vault/write,
// /vault/update, /vault/delete (see ./api.ts).
//
// The clarity payload type lives here because the phone app still attaches
// it to vault items when it ships transcripts; keeping the shape definition
// in one place avoids drift when phone parity work picks up.

export type ProviderId = "claude" | "chatgpt" | "gemini" | "copilot" | "local";

export interface VaultClarityPayload {
  decisions: string[];
  warnings: string[];
  contradictions: Array<{ a: string; b: string; lineA: number; lineB: number; kind: string }>;
  pressure?: {
    sentenceCount: number;
    imperatives: number;
    urgencyWords: number;
    contradictions: number;
    hedgeRatio: number;
  };
  interpreters?: string[];
}
