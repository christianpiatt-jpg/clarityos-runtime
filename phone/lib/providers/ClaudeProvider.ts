import { Linking } from "react-native";
import * as Clipboard from "expo-clipboard";
import type { AIProvider } from "./types";

// TODO: when Claude exposes a deep-link scheme that accepts a prompt
// (e.g. claude://chat?prompt=...), wire it here. claude.ai/new does not
// take a query param today, so we copy the text to the clipboard and
// open the new-chat URL — the user pastes once they land.
export const ClaudeProvider: AIProvider = {
  id: "claude",
  name: "Claude",
  async sendMessage(text: string) {
    try {
      await Clipboard.setStringAsync(text);
      await Linking.openURL("https://claude.ai/new");
      return { success: true, message: "Opened Claude. Prompt copied to clipboard — paste to send." };
    } catch (e: any) {
      return { success: false, message: e?.message || "Could not open Claude" };
    }
  },
};
