import type { AIProvider } from "./types";

// Stub for a future on-device LLM (executorch / llama.cpp via a native
// module / ONNX Runtime / WebGPU on Expo Web, etc.). Mirrors the contract
// so screens can already wire it up — they'll just see a friendly
// "not implemented yet" until a real engine lands here.
export const LocalProvider: AIProvider = {
  id: "local",
  name: "Local (on-device)",
  async sendMessage(_text: string) {
    return { success: false, message: "Local provider not implemented yet" };
  },
};
