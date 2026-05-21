import AsyncStorage from "@react-native-async-storage/async-storage";
import type { ProviderId } from "./providers/types";

export const storage = {
  get: (k: string) => AsyncStorage.getItem(k),
  set: (k: string, v: string) => AsyncStorage.setItem(k, v),
  remove: (k: string) => AsyncStorage.removeItem(k),
  multiRemove: (ks: string[]) => AsyncStorage.multiRemove(ks),
};

export const KEYS = {
  session: "clarityos_session",
  user: "clarityos_user",
  threads: "clarityos_threads",
  activeThread: "clarityos_active_thread",
  engine: "clarityos_engine",
  mode: "clarityos_mode",
  apiBaseOverride: "clarityos_api_base",
  aiProvider: "clarityos.aiProvider",
  interrupted: "clarityos.interrupted",
  // v62 / Unit 45 — Operator session runtime resume pointer.
  // Mirrors web's clarityos_session_resume_id localStorage key.
  operatorSessionResumeId: "clarityos_session_resume_id",
} as const;

const VALID_PROVIDERS: ReadonlyArray<ProviderId> = ["claude", "chatgpt", "gemini", "copilot", "local"];

export async function getAIProvider(): Promise<ProviderId | null> {
  const raw = await AsyncStorage.getItem(KEYS.aiProvider);
  if (raw && (VALID_PROVIDERS as readonly string[]).includes(raw)) {
    return raw as ProviderId;
  }
  return null;
}

export async function setAIProvider(id: ProviderId): Promise<void> {
  await AsyncStorage.setItem(KEYS.aiProvider, id);
}
