import { Linking } from "react-native";
import * as Clipboard from "expo-clipboard";
import type { AIProvider } from "./types";

// TODO: Gemini's web URL accepts no prefilled prompt today. The Android
// "Hey Google, ask Gemini..." Assistant intent could carry text, but
// that requires a native intent on Android only — out of scope for now.
export const GeminiProvider: AIProvider = {
  id: "gemini",
  name: "Gemini",
  async sendMessage(text: string) {
    try {
      await Clipboard.setStringAsync(text);
      await Linking.openURL("https://gemini.google.com/");
      return { success: true, message: "Opened Gemini. Prompt copied to clipboard — paste to send." };
    } catch (e: any) {
      return { success: false, message: e?.message || "Could not open Gemini" };
    }
  },
};
