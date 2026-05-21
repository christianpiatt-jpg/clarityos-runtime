import { Linking } from "react-native";
import * as Clipboard from "expo-clipboard";
import type { AIProvider } from "./types";

// TODO: ChatGPT iOS/Android apps register `chatgpt://` but the documented
// surface for prefilled prompts is unstable. For now: clipboard + web URL.
export const ChatGPTProvider: AIProvider = {
  id: "chatgpt",
  name: "ChatGPT",
  async sendMessage(text: string) {
    try {
      await Clipboard.setStringAsync(text);
      await Linking.openURL("https://chat.openai.com/");
      return { success: true, message: "Opened ChatGPT. Prompt copied to clipboard — paste to send." };
    } catch (e: any) {
      return { success: false, message: e?.message || "Could not open ChatGPT" };
    }
  },
};
