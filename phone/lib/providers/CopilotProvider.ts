import { Linking } from "react-native";
import * as Clipboard from "expo-clipboard";
import type { AIProvider } from "./types";

// TODO: Copilot's web does support a `?q=` query param on
// copilot.microsoft.com — confirm + URL-encode and replace the
// clipboard fallback when ready. Today: clipboard + open root.
export const CopilotProvider: AIProvider = {
  id: "copilot",
  name: "Copilot",
  async sendMessage(text: string) {
    try {
      await Clipboard.setStringAsync(text);
      await Linking.openURL("https://copilot.microsoft.com/");
      return { success: true, message: "Opened Copilot. Prompt copied to clipboard — paste to send." };
    } catch (e: any) {
      return { success: false, message: e?.message || "Could not open Copilot" };
    }
  },
};
